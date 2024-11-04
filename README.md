## x.ai Grok IRC Chat Bot
Edit the chat_grok.conf and keywords in the .py file to your preferred liking. Be sure to put the bot's nick in the keywords section as it only responds to keywords added.

Replace xai-REDACTED with your API key found here: https://console.x.ai/

Grok IRC Bot is a (kinda) fork of https://github.com/knrd1/chatgpt but using x.ai's less woke API and a few other subtle modifications catered for me.

X's xAI SDK reference: https://docs.x.ai/api/integrations#openai-sdk

Hail Elon! jeje j/k!

```bash
pip3 install openai==0.28 pyshorteners
mkdir -p grokbot
cd grokbot
vim grok001.conf # Edit context, server, channel, nickname, ident and realname
vim grok001.py # Edit the file by adding the bot's nick and keywords
screen -S grokbot # Add to a screen session
python grok001.py # Run the bot and enjoy
