# Set of psycological tests for traders to audit chances for success

## Project history

For nearly 6 years of my life I was doing a lot of cryptotrading, and got into the circle of many successfull traders, as well as some trading influencers. \
One of them asked me to develop an MVP for a service, that would allow traders to understand if their psycological profile has chances of making money from this long term, which I successfully did. 

Guys conducted a big research, that allowed them to know if trader is good for the role based on IQ, ATQ, and Trail Making Tests. \
As project funding was very limited, it was decided to make first version of automation as a telegram bot with IQ and ATQ tests, and take Trail Making Test as part of final online call with the results.

The only input I was given is the requirement to make good stuff, however, in the end, I was able to get iq and atq questions in a form of internet links. 

## Results

Telegram bot that's available [in here](https://t.me/dt_trader_bot) is a very fast MVP targeted to test the hypothesys of making money with trader's analytics. Currently in the state of checking. \
I was able to do everything myself, including improving texts, creating images, implementing business logic, and other tasks.

The code is absolutely unsustainable, but it was done mostly on purpose, as noone needed to save this project past MVP. project was done in about two weeks of active work, as it can be seen in commit history. 

As of today, the only big flaw outside of code quality is no safe deploys, as job queue doesn't save it's state when exiting the application. This should be done first thing, in case if application will be maintained. 

## Set up instructions

Make sure you have MongoDB running\
Create .env file using the provided example

Run using docker or python3.11+ by taking commands from either github action files, or .vscode config repo directory
