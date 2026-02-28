import configparser
import socket
import ssl
import time
import requests
import json
import os
import random
import datetime
import re

# Load configuration
config = configparser.ConfigParser()
config.read("grok.conf")

XAI_API_KEY = config.get('grok', 'api_key')
model = config.get('chatcompletion', 'model')
context_file = config.get('chatcompletion', 'context_file')
temperature = config.getfloat('chatcompletion', 'temperature')
max_tokens = config.getint('chatcompletion', 'max_tokens')
top_p = config.getfloat('chatcompletion', 'top_p')
frequency_penalty = config.getfloat('chatcompletion', 'frequency_penalty')
presence_penalty = config.getfloat('chatcompletion', 'presence_penalty')
request_timeout = config.getint('chatcompletion', 'request_timeout')
use_top_p = config.getboolean('chatcompletion', 'use_top_p')
use_frequency_penalty = config.getboolean('chatcompletion', 'use_frequency_penalty')
use_presence_penalty = config.getboolean('chatcompletion', 'use_presence_penalty')
use_live_search = config.getboolean('chatcompletion', 'use_live_search')

server = config.get('irc', 'server')
port = config.getint('irc', 'port')
use_ssl = config.getboolean('irc', 'ssl')
channels = config.get('irc', 'channels').split(',')
nickname = config.get('irc', 'nickname')
ident = config.get('irc', 'ident')
realname = config.get('irc', 'realname')
keywords = [k.strip() for k in config.get('irc', 'keywords').split(',')]
ignore_file = config.get('irc', 'ignore_file')

authorized_users = [u.strip() for u in config.get('security', 'authorized_users').split(',')]
allowed_modes = [m.strip() for m in config.get('security', 'allowed_modes').split(',')]

# Memory and log files
MEMORY_FILE = "chat_memory.json"
CHANNEL_LOG_FILE = "channel_logs.json"
OPTOUT_FILE = "optout_users.json"

# User-specific memory functions
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def get_recent_memory(memory, user, limit=50):
    return memory.get(user, [])[-limit:]

def add_to_memory(memory, user, role, content):
    if user not in memory:
        memory[user] = []
    memory[user].append({"role": role, "content": content})
    save_memory(memory)

# Channel log functions
def load_channel_logs():
    if os.path.exists(CHANNEL_LOG_FILE):
        with open(CHANNEL_LOG_FILE, "r") as f:
            logs = json.load(f)
        one_day_ago = datetime.datetime.now() - datetime.timedelta(hours=72)
        return [log for log in logs if datetime.datetime.fromisoformat(log["timestamp"]) > one_day_ago]
    return []

def save_channel_logs(logs):
    with open(CHANNEL_LOG_FILE, "w") as f:
        json.dump(logs, f)

def add_to_channel_logs(channel, user, message):
    optout_users = load_optout_users()
    if user not in optout_users:
        logs = load_channel_logs()
        timestamp = datetime.datetime.now()
        logs.append({
            "channel": channel,
            "user": user,
            "message": message,
            "timestamp": timestamp.isoformat()
        })
        logs = logs[-500:]
        save_channel_logs(logs)

# Opt-out functions
def load_optout_users():
    if os.path.exists(OPTOUT_FILE):
        with open(OPTOUT_FILE, "r") as f:
            return json.load(f)
    return []

def save_optout_users(users):
    with open(OPTOUT_FILE, "w") as f:
        json.dump(users, f)

# Ignore functions
def load_ignored_users():
    if os.path.exists(ignore_file):
        try:
            with open(ignore_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []

def save_ignored_users(users):
    with open(ignore_file, "w") as f:
        json.dump(users, f)

# External Context
def load_context():
    try:
        with open(context_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: {context_file} not found, using empty context.")
        return ""

# Clean citations from API responses
def clean_citations(text):
    # Convert markdown citations [[1]](url) to plain URLs
    text = re.sub(r'\[\[\d+\]\]\((https?://\S+?)\)', r' \1', text)
    # Also handle standard markdown links [text](url)
    text = re.sub(r'\[([^\]]+)\]\((https?://\S+?)\)', r'\1 \2', text)
    # Strip grok XML citation tags
    text = re.sub(r'<grok:render[^>]*>.*?</grok:render>', '', text, flags=re.DOTALL)
    # Strip any leftover <argument> tags
    text = re.sub(r'<argument[^>]*>.*?</argument>', '', text, flags=re.DOTALL)
    # Clean up extra whitespace
    text = re.sub(r'  +', ' ', text).strip()
    return text

# Get weather
def get_weather(location):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(location)}&count=1"
        geo_resp = requests.get(geo_url, timeout=10).json()
        if "results" not in geo_resp or not geo_resp["results"]:
            return f"Could not find location: {location}"

        place = geo_resp["results"][0]
        lat = place["latitude"]
        lon = place["longitude"]
        name = place.get("name", location)
        country = place.get("country", "")

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&temperature_unit=fahrenheit"
            f"&wind_speed_unit=mph"
            f"&forecast_days=3"
            f"&timezone=auto"
        )
        weather_resp = requests.get(weather_url, timeout=10).json()

        current = weather_resp["current"]
        daily = weather_resp["daily"]

        weather_info = f"Current weather in {name}, {country}: "
        weather_info += f"Temperature: {current['temperature_2m']}°F, "
        weather_info += f"Humidity: {current['relative_humidity_2m']}%, "
        weather_info += f"Wind: {current['wind_speed_10m']} mph. "
        weather_info += "Forecast: "

        for i in range(len(daily["time"])):
            weather_info += (
                f"{daily['time'][i]}: "
                f"High {daily['temperature_2m_max'][i]}°F, "
                f"Low {daily['temperature_2m_min'][i]}°F, "
                f"Precipitation chance {daily['precipitation_probability_max'][i]}%. "
            )

        return weather_info

    except Exception as e:
        print(f"Weather error: {e}")
        return "Could not retrieve weather data."

# Get Grok response
def get_grok_response(question, recent_memory, user_nickname):
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }

    channel_logs = load_channel_logs()
    question_lower = question.lower()

    # Check for weather-related questions
    weather_info = ""
    weather_patterns = ["weather", "forecast", "temperature", "how hot", "how cold", "rain"]
    if any(pattern in question_lower for pattern in weather_patterns):
        location = None
        for prep in [" in ", " for ", " at "]:
            if prep in question_lower:
                location = question.split(prep)[-1].strip().rstrip("?.,!")
                break
        if location:
            weather_info = get_weather(location)

    # Check for time/date questions
    time_info = ""
    time_patterns = ["what time", "current time", "what date", "today's date", "what day", "date today", "time is it"]
    if any(pattern in question_lower for pattern in time_patterns):
        now = datetime.datetime.now()
        time_info = f"The current server date and time is: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}"

    # Build system prompt
    system_prompt = f"{load_context()} Address the user as {user_nickname} in your responses. When asked to summarize conversations, provide a concise summary of the main topics discussed in the provided channel logs. When asked about what a specific user said, accurately quote or paraphrase their most recent message from the logs. Use the provided conversation history for context."
    if weather_info:
        system_prompt += f" Here is current weather data to use in your response: {weather_info}"
    if time_info:
        system_prompt += f" {time_info}"

    # Determine relevant logs
    is_summary = "summarize" in question_lower or "summary" in question_lower
    specific_user = None
    if "what did" in question_lower:
        for log in channel_logs[::-1]:
            if log["user"] != user_nickname and log["user"].lower() in question_lower:
                specific_user = log["user"]
                break

    if is_summary:
        relevant_logs = channel_logs[-50:]
    elif specific_user:
        relevant_logs = [log for log in channel_logs if log["user"] == specific_user][-10:]
        if not relevant_logs:
            relevant_logs = channel_logs[-25:]
    else:
        relevant_logs = [
            log for log in channel_logs
            if log["user"] == user_nickname or any(keyword in log["message"].lower() for keyword in keywords)
        ][-5:]

    print("Relevant Logs:", json.dumps(relevant_logs, indent=4))

    log_messages = [
        {"role": "user" if log["user"] == user_nickname else "assistant", "content": f"{log['user']}: {log['message']}"}
        for log in relevant_logs
    ]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(log_messages)
    messages.extend(recent_memory)
    messages.append({"role": "user", "content": f"{user_nickname}: {question}"})

    # Determine if this is a news/search query
    news_patterns = ["news", "latest", "trending", "headline", "what happened",
                     "update on", "current events", "search", "find out", "look up",
                     "who won", "score", "stock", "price of"]
    needs_search = use_live_search and any(pattern in question_lower for pattern in news_patterns)

    if needs_search:
        # Use Responses API with search tools
        url = "https://api.x.ai/v1/responses"
        data = {
            "model": model,
            "input": messages,
            "tools": [
                {"type": "web_search"},
                {"type": "x_search"}
            ]
        }
    else:
        # Use standard Chat Completions API
        url = "https://api.x.ai/v1/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if use_top_p:
            data["top_p"] = top_p
        if use_frequency_penalty:
            data["frequency_penalty"] = frequency_penalty
        if use_presence_penalty:
            data["presence_penalty"] = presence_penalty

    print("Payload:", json.dumps(data, indent=4))

    try:
        response = requests.post(url, headers=headers, json=data, timeout=request_timeout)
        response.raise_for_status()

        response_data = response.json()
        print("Response:", json.dumps(response_data, indent=4))

        if needs_search:
            result_text = ""
            source_urls = []
            for item in response_data.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            result_text = content.get("text", "")
                elif item.get("type") == "search_result":
                    sr_url = item.get("url", "")
                    if sr_url and sr_url not in source_urls:
                        source_urls.append(sr_url)
            result_text = clean_citations(result_text)
            if source_urls:
                result_text += " | Sources: " + " , ".join(source_urls[:5])
            return result_text if result_text else "Sorry, no results found."
        else:
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

# IRC connection
def connect_irc():
    while True:
        try:
            irc = socket.create_connection((server, port), timeout=30)
            if use_ssl:
                irc = ssl.wrap_socket(irc)
            irc.send(bytes(f"USER {ident} 0 * :{realname}\n", "UTF-8"))
            irc.send(bytes(f"NICK {nickname}\n", "UTF-8"))
            print(f"Connected to IRC server: {server}")

            empty_count = 0
            while True:
                data = irc.recv(4096).decode("UTF-8", errors="ignore")
                print(f"Received: {data}")

                if not data.strip():
                    empty_count += 1
                    if empty_count >= 5:
                        print("Connection died during handshake. Retrying...")
                        irc.close()
                        break
                    continue
                else:
                    empty_count = 0

                if "001" in data:
                    print("Successfully connected. Joining channels...")
                    for channel in channels:
                        irc.send(bytes(f"JOIN {channel}\n", "UTF-8"))
                        print(f"Joining channel: {channel}")
                    irc.settimeout(None)
                    return irc
                elif data.startswith("PING"):
                    irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        except Exception as e:
            print(f"Connection failed: {e}")
            try:
                irc.close()
            except:
                pass
            time.sleep(10)

# Main loop
def main():
    while True:
        try:
            irc = connect_irc()
            memory = load_memory()
            chat_sessions = {}
            session_duration = 2
            version_response = "IRC Grok Bot by m0n https://github.com/timmo-x/irc_grokbot"
            empty_count = 0

            while True:
                data = irc.recv(4096).decode("UTF-8", errors="ignore")

                # Detect dead connection (repeated empty receives)
                if not data.strip():
                    empty_count += 1
                    if empty_count >= 5:
                        print("Connection lost (repeated empty receives). Reconnecting...")
                        irc.close()
                        break
                    continue
                else:
                    empty_count = 0

                print(f"Received: {data}")

                if data.startswith("PING"):
                    irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))

                elif " INVITE " in data:
                    inviting_user = data.split('!')[0][1:]
                    invited_channel = data.split(':')[-1].strip()
                    if inviting_user in authorized_users:
                        irc.send(bytes(f"JOIN {invited_channel}\n", "UTF-8"))
                        print(f"Accepted invite from {inviting_user} to {invited_channel}")
                    else:
                        print(f"Ignored invite from unauthorized user {inviting_user} to {invited_channel}")

                elif "PRIVMSG" in data:
                    user = data.split('!')[0][1:]
                    message = ':'.join(data.split(':')[2:]).strip()
                    channel = data.split(' PRIVMSG ')[-1].split(' :')[0]

                    # Skip ignored users entirely
                    if user in load_ignored_users():
                        continue

                    add_to_channel_logs(channel, user, message)

                    if message == "\001VERSION\001":
                        irc.send(bytes(f"NOTICE {user} :\001VERSION {version_response}\001\n", "UTF-8"))
                        print(f"Sent CTCP VERSION response to {user}: {version_response}")
                        continue
                    elif message == "!info":
                        irc.send(bytes(f"PRIVMSG {channel} :This bot logs channel messages to provide context for responses. Use !optout to exclude your messages.\n", "UTF-8"))
                        continue
                    elif message == "!optout":
                        optout_users = load_optout_users()
                        if user not in optout_users:
                            optout_users.append(user)
                            save_optout_users(optout_users)
                            irc.send(bytes(f"PRIVMSG {channel} :{user}, you have opted out of message logging.\n", "UTF-8"))
                        continue
                    elif message.startswith("!search "):
                        query = message[8:].lower()
                        relevant_logs = [log for log in load_channel_logs() if query in log["message"].lower()][-3:]
                        if relevant_logs:
                            response = f"{user}, found these: " + "; ".join(f"{log['user']}: {log['message']}" for log in relevant_logs)
                        else:
                            response = f"{user}, nothing found for '{query}'."
                        irc.send(bytes(f"PRIVMSG {channel} :{response}\n", "UTF-8"))
                        continue

                    current_time = time.time()
                    active_session = user in chat_sessions and (current_time - chat_sessions[user] < session_duration)

                    if any(keyword in message.lower() for keyword in keywords):
                        chat_sessions[user] = current_time
                        active_session = True

                    if active_session:
                        chat_sessions[user] = current_time
                        question = message.strip()
                        recent_memory = get_recent_memory(memory, user)
                        answer = get_grok_response(question, recent_memory, user)
                        answer = clean_citations(answer)
                        add_to_memory(memory, user, "user", question)
                        add_to_memory(memory, user, "assistant", answer)

                        response_channel = channel if channel != nickname else user
                        answer_lines = answer.split('\n')
                        for line in answer_lines:
                            stripped = line.strip()

                            # Handle IRC mode commands returned by the AI
                            mode_match = re.search(r'\[MODE\s+(#\S+)\s+([+-][ovaqOVAQ])\s+(.+?)\]', stripped)
                            if mode_match:
                                target_channel = mode_match.group(1)
                                mode = mode_match.group(2)
                                nicks = mode_match.group(3).split()
                                if user in authorized_users and mode in allowed_modes:
                                    mode_char = mode[0]
                                    mode_letter = mode[1]
                                    mode_string = mode_char + (mode_letter * len(nicks))
                                    raw_cmd = f"MODE {target_channel} {mode_string} {' '.join(nicks)}"
                                    irc.send(bytes(f"{raw_cmd}\n", "UTF-8"))
                                    print(f"Executed IRC command from {user}: {raw_cmd}")
                                else:
                                    irc.send(bytes(f"PRIVMSG {response_channel} :Nice try, but no.\n", "UTF-8"))
                                continue

                            # Handle ignore commands returned by the AI
                            ignore_match = re.search(r'\[IGNORE\s+(\S+)\]', stripped)
                            if ignore_match:
                                target = ignore_match.group(1)
                                if user in authorized_users:
                                    ignored = load_ignored_users()
                                    if target not in ignored:
                                        ignored.append(target)
                                        save_ignored_users(ignored)
                                    irc.send(bytes(f"PRIVMSG {response_channel} :{target} is now ignored.\n", "UTF-8"))
                                else:
                                    irc.send(bytes(f"PRIVMSG {response_channel} :Nice try, but no.\n", "UTF-8"))
                                continue

                            # Handle unignore commands returned by the AI
                            unignore_match = re.search(r'\[UNIGNORE\s+(\S+)\]', stripped)
                            if unignore_match:
                                target = unignore_match.group(1)
                                if user in authorized_users:
                                    ignored = load_ignored_users()
                                    if target in ignored:
                                        ignored.remove(target)
                                        save_ignored_users(ignored)
                                    irc.send(bytes(f"PRIVMSG {response_channel} :{target} is no longer ignored.\n", "UTF-8"))
                                else:
                                    irc.send(bytes(f"PRIVMSG {response_channel} :Nice try, but no.\n", "UTF-8"))
                                continue

                            line_parts = [line[i:i+400] for i in range(0, len(line), 400)]
                            for part in line_parts:
                                delay = random.uniform(0, 1)
                                time.sleep(delay)
                                irc.send(bytes(f"PRIVMSG {response_channel} :{part}\n", "UTF-8"))

                    chat_sessions = {user: timestamp for user, timestamp in chat_sessions.items() if current_time - timestamp < session_duration}

        except Exception as e:
            print(f"Error in main loop: {e}. Reconnecting in 10 seconds...")
            try:
                irc.close()
            except:
                pass
            time.sleep(10)

if __name__ == "__main__":
    main()
