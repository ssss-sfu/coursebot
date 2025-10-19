from dotenv import load_dotenv
import discord
import os

load_dotenv()  # Load environment variables from .env file
discord_token = os.getenv('DISCORD_TOKEN')

# Creates an instance of a client. This is our conneciton to discord.
intents = discord.Intents.default() 
intents.message_content = True # Enable message content intent
# Registers an event. This event is called when the bot has switched from offline to online.
client = discord.Client(intents=intents) # Create a client instance with specified intents
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    
@client.event
async def on_message(message):
    # we ignore messages from the bot itself to prevent infinite loops
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run(discord_token)