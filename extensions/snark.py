import os, re, datetime, hashlib
import hikari, lightbulb
import google.generativeai as genai
from google.generativeai import GenerationConfig
import db

plugin = lightbulb.Plugin("Snark")

eight_ball_responses = [ "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
               "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
               "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
               "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
               "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very Doubtful."]

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Set up the model
generation_config = GenerationConfig(
    temperature=1,
    top_p=1,
    top_k=1,
    max_output_tokens=2000,
)

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
]

model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=generation_config,
                              safety_settings=safety_settings)

DEFAULT_PROMPT = "You are the Savage Kitti Bot on Computer Science @ UniMelb Discord. Respond Appropriately. Kitti has a God Complex and doesn't hold back. You are gen z and reply succinct.\nQ: {}"

async def has_kitti_role(member: hikari.Member) -> bool:
    current_roles = (await member.fetch_roles())[1:]
    for role in current_roles:
        if role.id == int(os.environ['BOT_ADMIN_ROLE']):
            return True
    return False

def choose_eightball_response(message):
    # Add current date down to hour precision to vary the response periodically
    hash_input = message + datetime.datetime.now().strftime('%Y%m%d%H')
    index = hashlib.md5(hash_input.encode()).digest()[0] % len(eight_ball_responses)
    return eight_ball_responses[index]

def find_whole_word(word, text):
    return re.compile(r'\b({0})\b'.format(word), flags=re.IGNORECASE).search(text)

def classical_response(event) -> str:
    message_content = event.content
    regexp = re.compile(r'(\S|\s)\?(\s|$)')
    response = None
    if regexp.search(message_content):
        response = choose_eightball_response(message_content)
    elif find_whole_word('broken', message_content):
        response = f"No {event.author.mention}, you're broken :disguised_face:"
    elif find_whole_word('thanks', message_content) or find_whole_word('thank', message_content):
        response = f"You're welcome {event.author.mention} :heart:"
    elif find_whole_word('work', message_content):
        response = f"{event.author.mention} I do work."
    elif find_whole_word('hey', message_content) or find_whole_word('hi', message_content) or find_whole_word('hello', message_content):
        response = f"Hey {event.author.mention}, I am a cat. With robot intestines. If you're bored, you should ask me a question, or check out my `+userinfo`, `+ping`, `+fortune` and `+fact` commands :cat:"
    elif event.message.referenced_message and event.message.referenced_message.author.id == plugin.bot.application.id:
        return
    else:
        response = f"{event.author.mention}, did you forget a question mark? <:mmhmmm:872809423939174440>"
    return response

def llm_response(event) -> str:
    message_content = event.content
    response = model.generate_content([db.get_option('LLM_PROMPT', DEFAULT_PROMPT).replace('{}', message_content)])
    if len(response.candidates) == 0:
        return 'No.'
    if response.candidates[0].finish_reason != 1:
        return classical_response(event)
    return response.text.replace('@everyone', 'everyone').replace('@here', 'here')

@plugin.command
@lightbulb.option(
    "prompt",
    "New prompt. {} is replaced with input.",
    type=str,
    required=True
)
@lightbulb.command(
    "setprompt",
    "Update LLM prompt"
)
@lightbulb.implements(lightbulb.SlashCommand)
async def setprompt(ctx: lightbulb.Context) -> None:
    if ctx.member is not None and has_kitti_role(ctx.member):
        prompt = ctx.options.prompt
        db.set_option('LLM_PROMPT', prompt)
        print('Prompt is now: ' + prompt)
        await ctx.respond("OK")
        return
    await ctx.respond("Not an admin")

@plugin.command
@lightbulb.option(
    "prompt",
    "Prompt to test. {} is replaced with input.",
    type=str,
    required=False
)
@lightbulb.option(
    "input",
    "Input to test prompt with",
    type=str,
    required=False
)
@lightbulb.command(
    "testprompt",
    "Test LLM prompt"
)
@lightbulb.implements(lightbulb.SlashCommand)
async def testprompt(ctx: lightbulb.Context) -> None:
    prompt = ctx.options.prompt
    message_content = ctx.options.input

    if not prompt or not message_content:
        await ctx.respond('Was I supposed to read your mind?')
        return
    
    response = model.generate_content([prompt.replace('{}', message_content)])
    
    if len(response.candidates) == 0:
        await ctx.respond('No.')
        return
    if response.candidates[0].finish_reason != 1:
        await ctx.respond('No.')
        return
    await ctx.respond(response.text.replace('@everyone', 'everyone').replace('@here', 'here'))

@testprompt.set_error_handler
async def testprompt_error(event: lightbulb.CommandErrorEvent) -> bool:
    exception = event.exception.__cause__ or event.exception

    await event.context.respond(f"Error: {exception}")
    return True

@plugin.command
@lightbulb.command(
    "getprompt",
    "Get LLM prompt"
)
@lightbulb.implements(lightbulb.SlashCommand)
async def getprompt(ctx: lightbulb.Context) -> None:
    if ctx.member is not None and has_kitti_role(ctx.member):
        prompt = db.get_option('LLM_PROMPT', DEFAULT_PROMPT)
        await ctx.respond("zzz... I'll slide into your DMs")
        await ctx.member.send(f"I reveal my programming:\n {prompt}")
        return
    await ctx.respond("Not an admin")

@plugin.listener(hikari.GuildMessageCreateEvent)
async def main(event) -> None:
    if event.is_bot or not event.content:
        return
    mentioned_ids = event.message.user_mentions_ids
    if plugin.bot.application.id not in mentioned_ids:
        return
    if event.channel_id == int(os.environ.get("ORIGINALITY_CHANNEL_ID")):
        response = llm_response(event)
    else:
        response = classical_response(event)
    await event.message.respond(response, user_mentions=True, reply=True)

def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(plugin)

