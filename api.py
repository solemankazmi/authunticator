from fastapi import FastAPI
import uvicorn
import re
import random
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_random_greetings(time_in_hour,name):
    """
    get the greetings from presets
    """
    lines=[]
    with open('greetings.txt') as f:
        lines = [line.rstrip('\n') for line in f]
    
    line = random.choice(lines)
    line = re.sub("^\d{0,}. ", "", line)
    
    current_hour = time_in_hour
    if current_hour<12:
        time = 'Good morning'
    elif 12<=current_hour<18:
        time = 'Good afternoon'
    else:
        time = 'Good Evening'
    line = line.format(time=time, name=name)
    return line

@app.get("/get_greetings/")

async def main_taining_bot(current_hour:int, name: str):
    
    response = get_random_greetings(current_hour, name)
    
    return {"response" : response}
    
    
    
if __name__ == '__main__':
    
    uvicorn.run(app, host="0.0.0.0", port=8094)
