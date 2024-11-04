import configparser
import socket
import ssl
import time
import requests
import json
import os

# Load configuration
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

# Define keywords to trigger the bot
keywords = ["bot", "grok", "ai", "assistant"]  # Add keywords here

# Added memory file for storing conversation history! At least the last 10 chats.
MEMORY_FILE = "chat_memory.json"

# Load or initialize memory
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

# Retrieve recent memory context for a channel or user
def get_recent_memory(memory, identifier, limit=10):
    return memory.get(identifier, [])[-limit:]

# Store a message in memory
def add_to_memory(memory, identifier, role, content):
    if identifier not in memory:
        memory[identifier] = []
    memory[identifier].append({"role": role, "content": content})
    save_memory(memory)

# Function to fetch response from Grok API directly using requests
def get_grok_response(question, recent_memory):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Build the conversation context
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
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=request_timeout)
        response.raise_for_status()
        
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
        
    except json.JSONDecodeError:
        print("Error: Unable to parse JSON response.")
        return "Sorry, I encountered an error."
    except KeyError:
        print("Error: Expected data not found in the response.")
        return "Sorry, something went wrong."
    except requests.exceptions.RequestException as e:
        print(f"Unexpected error: {e}")
        return "Sorry, an unexpected error occurred."

# Connect to IRC and wait for server confirmation before joining channels
def connect_irc():
    while True:
        try:
            irc = socket.create_connection((server, port))
            if use_ssl:
                irc = ssl.wrap_socket(irc)
            irc.send(bytes(f"USER {ident} 0 * :{realname}\n", "UTF-8"))
            irc.send(bytes(f"NICK {nickname}\n", "UTF-8"))
            print(f"Connected to IRC server: {server}")

            # Wait for the connection welcome message (code 001)
            while True:
                data = irc.recv(4096).decode("UTF-8", errors="ignore")
                print(f"Received: {data}")
                
                if "001" in data:  # 001 signifies successful connection
                    print("Successfully connected. Joining channels...")
                    for channel in channels:
                        irc.send(bytes(f"JOIN {channel}\n", "UTF-8"))
                        print(f"Joining channel: {channel}")
                    return irc
                elif data.startswith("PING"):
                    # Respond to PING to keep the connection alive
                    irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(5)

# Main function to listen and respond
def main():
    irc = connect_irc()
    memory = load_memory()  # Load memory at start
    while True:
        data = irc.recv(4096).decode("UTF-8", errors="ignore")
        print(f"Received: {data}")

        if data.startswith("PING"):
            irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        
        elif "PRIVMSG" in data:
            user = data.split('!')[0][1:]
            message = ':'.join(data.split(':')[2:])
            channel = data.split(' PRIVMSG ')[-1].split(' :')[0]
            
            # Check if the message contains any keyword
            if any(keyword in message.lower() for keyword in keywords):
                question = message.strip()
                
                # Retrieve recent context for the channel or user
                identifier = channel if channel != nickname else user
                recent_memory = get_recent_memory(memory, identifier)
                
                answer = get_grok_response(question, recent_memory)
                
                # Store the interaction in memory
                add_to_memory(memory, identifier, "user", question)
                add_to_memory(memory, identifier, "assistant", answer)

                # Respond in channel or private message
                response_channel = channel if channel != nickname else user
                irc.send(bytes(f"PRIVMSG {response_channel} :{answer}\n", "UTF-8"))

if __name__ == "__main__":
    main()
