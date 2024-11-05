## x.ai Grok IRC Chat Bot
Best darn IRC AI chat bot on the planet! xAI API doesn't hold back and is very candid unlike chatgpt.

Edit the grok.conf and keywords in the .py file to your preferred liking. Be sure to put the bot's nick in the keywords section as it only responds to keywords you've added.

Memory can be increased or decreased by this line: def get_recent_memory(memory, identifier, limit=10):

Replace xai-REDACTED with your API key found here: https://console.x.ai/

Grok IRC Bot is (kinda) forked from https://github.com/knrd1/chatgpt but using x.ai's less woke API and a few other huge modifications catered for my tastes.

X's xAI SDK reference: https://docs.x.ai/api/integrations#openai-sdk

You may need a pretentious x.com premium account and blue check like I have to access Grok's API.

Need help? /join #s💀l on irc.undernet.org

Hail Elon! jeje j/k!

```bash
pip3 install openai==0.28 pyshorteners
mkdir -p grokbot
cd grokbot
vim grok.conf # Edit context, server, channel, nickname, ident and realname
vim grokbot.py # Edit the file by adding the bot's nick and keywords
screen -S grokbot # Add to a screen session
python grok001.py # Run the bot and enjoy
