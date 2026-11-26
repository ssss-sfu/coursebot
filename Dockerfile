# downloads a prebuild docker image with python 3.13 installed. slim is more lighweight
FROM python:3.13-slim
# sets /app as the working directory, all commands run from here
WORKDIR /app
ENV PYTHONUNBUFFERED=1
# copies requirements.txt file from local machine into the app directory.
COPY requirements.txt .
# installs python packages listed in requirements
# --no-cache-dir flag prevents pip from storing cache files, reducing image size
RUN pip install --no-cache-dir -r requirements.txt
# copies al lfiles from project folder into containers /app directory
COPY . .

# creates a regular linux user named bot.
# user makes every later step run that instead of the root

RUN useradd --create-home --uid 10001 bot
USER bot

EXPOSE 8080
#defines default command to run when container starts
CMD ["python", "-m", "src.main"]
