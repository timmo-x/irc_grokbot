import configparser
import socket
import ssl
import time
import requests
import json

# Load configuration
config = configparser.ConfigParser()
config.read("chat_grok.conf")

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
password = config.get('irc', 'password')

# Define additional keywords to trigger the bot
keywords = [nickname.lower(), "bot", "grok", "ai", "assistant"]  # Add more keywords as needed

# Function to fetch response from Grok API directly using requests
def get_grok_response(question):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": question}
        ],
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
    while True:
        data = irc.recv(4096).decode("UTF-8", errors="ignore")
        print(f"Received: {data}")

        if data.startswith("PING"):
            irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        
        elif "PRIVMSG" in data:
            user = data.split('!')[0][1:]
            message = ':'.join(data.split(':')[2:])
            channel = data.split(' PRIVMSG ')[-1].split(' :')[0]
            
            # Check if the message contains any keyword or if it's a private message
            if any(keyword in message.lower() for keyword in keywords) or channel == nickname:
                question = message.split(nickname, 1)[-1].strip() if nickname in message else message.strip()
                answer = get_grok_response(question)
                response_channel = channel if channel != nickname else user  # respond in channel or PM the user
                irc.send(bytes(f"PRIVMSG {response_channel} :{answer}\n", "UTF-8"))

if __name__ == "__main__":
    main()
