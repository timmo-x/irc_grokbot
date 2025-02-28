import configparser
import socket
import ssl  
import time 
import requests
import json     
import os       
import random
                
config = configparser.ConfigParser()
config.read("grok.conf")
                        
XAI_API_KEY = config.get('grok', 'api_key')
model = config.get('chatcompletion', 'model')
context = config.get('chatcompletion', 'context')
temperature = config.getfloat('chatcompletion', 'temperature')
max_tokens = config.getint('chatcompletion', 'max_tokens')
top_p = config.getfloat('chatcompletion', 'top_p')
frequency_penalty = config.getfloat('chatcompletion', 'frequency_penalty')
presence_penalty = config.getfloat('chatcompletion', 'presence_penalty')
request_timeout = config.getint('chatcompletion', 'request_timeout')

server = config.get('irc', 'server')
port = config.getint('irc', 'port')
use_ssl = config.getboolean('irc', 'ssl')
channels = config.get('irc', 'channels').split(',')
nickname = config.get('irc', 'nickname')
ident = config.get('irc', 'ident')
realname = config.get('irc', 'realname')
        
keywords = ["bot", "grok", "ai", "assistant"]  # Add keywords here
            
MEMORY_FILE = "chat_memory.json"
            
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}   
                
def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)
            
def get_recent_memory(memory, user, limit=15):
    return memory.get(user, [])[-limit:]
                
def add_to_memory(memory, user, role, content):
    if user not in memory:
        memory[user] = []
    memory[user].append({"role": role, "content": content})
    save_memory(memory)
                
def get_grok_response(question, recent_memory):
    url = "https://api.x.ai/v1/chat/completions"
    headers = { 
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }               
                        
    messages = [{"role": "system", "content": context}]
    messages.extend(recent_memory)
    messages.append({"role": "user", "content": question})

    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty
    }

    # Debugging
    print("Payload:", json.dumps(data, indent=4))

    try:
        response = requests.post(url, headers=headers, json=data, timeout=request_timeout)
        response.raise_for_status()

        response_data = response.json()
        print("Response:", json.dumps(response_data, indent=4))
        return response_data['choices'][0]['message']['content']

    except json.JSONDecodeError:
        print("Error: Unable to parse JSON response.")
        return "Sorry, I encountered an error."
    except KeyError:
        print("Error: Expected data not found in the response.")
        return "Sorry, something went wrong."
    except requests.exceptions.RequestException as e:
        print(f"Unexpected error: {e}")
        if hasattr(e, 'response') and e.response:
            print("Response content:", e.response.text)
        return "Sorry, an unexpected error occurred."

def connect_irc():
    while True:
        try:
            irc = socket.create_connection((server, port))
            if use_ssl:
                irc = ssl.wrap_socket(irc)
            irc.send(bytes(f"USER {ident} 0 * :{realname}\n", "UTF-8"))
            irc.send(bytes(f"NICK {nickname}\n", "UTF-8"))
            print(f"Connected to IRC server: {server}")

            while True:
                data = irc.recv(4096).decode("UTF-8", errors="ignore")
                print(f"Received: {data}")

                if "001" in data:
                    print("Successfully connected. Joining channels...")
                    for channel in channels:
                        irc.send(bytes(f"JOIN {channel}\n", "UTF-8"))
                        print(f"Joining channel: {channel}")
                    return irc
                elif data.startswith("PING"):

                    irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(5)

def main():
    irc = connect_irc()
    memory = load_memory()
    version_response = "IRC Grok Bot by m0n https://github.com/timmo-x/irc_grokbot"

    while True:
        data = irc.recv(4096).decode("UTF-8", errors="ignore")
        print(f"Received: {data}")

        if data.startswith("PING"):
            irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))

        elif "PRIVMSG" in data:
            user = data.split('!')[0][1:]
            message = ':'.join(data.split(':')[2:]).strip()
            channel = data.split(' PRIVMSG ')[-1].split(' :')[0]

            if message == "\001VERSION\001":
                irc.send(bytes(f"NOTICE {user} :\001VERSION {version_response}\001\n", "UTF-8"))
                print(f"Sent CTCP VERSION response to {user}: {version_response}")
                continue

            if any(keyword in message.lower() for keyword in keywords):
                question = message.strip()

                recent_memory = get_recent_memory(memory, user)

                answer = get_grok_response(question, recent_memory)

                add_to_memory(memory, user, "user", question)
                add_to_memory(memory, user, "assistant", answer)

                response_channel = channel if channel != nickname else user
                answer_lines = answer.split('\n')
                for line in answer_lines:
                    line_parts = [line[i:i+400] for i in range(0, len(line), 400)]
                    for part in line_parts:
                        delay = random.uniform(0, 5)
                        time.sleep(delay)
                        irc.send(bytes(f"PRIVMSG {response_channel} :{part}\n", "UTF-8"))

if __name__ == "__main__":
    main()
