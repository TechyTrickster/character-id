import os
import sys
import requests
import asyncio
import re
import functools



async def sendMessageHelper(address, payload):
        output = requests.post(address, json = payload)
        return(output)



def generateSystemPromptLine(prompt):
    output = {"role": "system", "content": prompt}
    return(output)



def decodeMessageContent(data):
    output = data['choices'][0]['message']['content']
    return(output)



class LMStudioSession:
    def __init__(self, address, systemPrompt, config = ""):
        self.address = address
        self.systemPrompt = systemPrompt
        self.chatHistory = []
        self.waitingForResponse = False
        self.messages = [generateSystemPromptLine(systemPrompt)]
        self.messageHandle = "empty"

        if(config != ""):
            self.config = config
        else:
            self.config = {
                "temperature": 0.7, 
                "max_tokens": -1,
                "stream": False
            }
    
    
    def clearMessageHistory(self):
        self.messages = []
        prompt = generateSystemPromptLine(self.systemPrompt)
        self.messages.append(prompt)


    def sendMessage(self, message):
        self.waitingForResponse = True
        payload = {}
        payload.update(self.config)
        message = {"role": "user", "content": message}
        self.messages.append(message)
        payload['messages'] = self.messages
        self.messageHandle = asyncio.create_task(sendMessageHelper(self.address, payload))
    

    def isWaitingForResponse(self):
        self.waitingForResponse = not self.messageHandle.done()
        return(self.waitingForResponse)
    

    async def receiveMessage(self):
        output = {}
        if(self.waitingForResponse):
            while(not self.messageHandle.done()):
                await asyncio.sleep(0.2)
            
            self.waitingForResponse = False
            data = self.messageHandle.result()
            output = data.json()
            messageBlock = output['choices'][0]['message']
            self.messages.append(messageBlock)
        else:
            output = "no output"

        return(output)



async def characterFinder(inputPassages, characterFinderInstance: LMStudioSession, nameValidatorInstance: LMStudioSession):
    output = {
        'characters': set([]),
        'tagged passages': []
    }

    indexedPassages = zip(range(len(inputPassages)), inputPassages)

    for (index, chunk) in indexedPassages:
        print("starting loop")
        print("input chunk: " + chunk)
        goodResponseDetected = False
        characterBuffer = []
        characterList = []

        while(not goodResponseDetected): #check to see if the AI is following the prompt enough to be confident in it's output
            print("looping for good character ID")
            characterFinderInstance.sendMessage(chunk)
            data = await characterFinderInstance.receiveMessage()
            characterFinderInstance.clearMessageHistory()
            characterData = decodeMessageContent(data)
            print("raw response from character finder: " + characterData)
            characterBuffer = characterData.split('\n') #divide into multiple lines
            characterBuffer = list(filter(lambda x: None != (re.search('[0-9]+\.', x)), characterBuffer)) #only keep the lines that have a #. on them 
            characterBuffer = list(map(lambda x: x.lower(), characterBuffer)) #move everything to lower case for simplicity and matching purposes
            print("filtered response from character finder: " + str(characterBuffer))
            goodResponseDetected = not ((len(characterBuffer) == 0) and (not ("NAK" in characterData)))

        print("left character finder loop")
        print("analyzing character finder names for actual names.")
        for name in characterBuffer: #check if the character name really is a character name, drop anything that isn't
            print("name being analyzed: " + name)
            nameValidatorInstance.sendMessage(name)
            data = await nameValidatorInstance.receiveMessage()
            nameValidatorInstance.clearMessageHistory()
            choice = decodeMessageContent(data).lower()
            print("processed identifier response: " + choice)
            if("yes" in choice):
                characterList.append(name)

        #do an n^2 loop to remove similar duplicates? like Count Dracula and Dracula?
            
        buffer = {'index': index, 'text': chunk, 'character list': characterList}
        output['characters'].update(set(characterList))
        output['tagged passages'].append(buffer)
        print("saved data")
        print(buffer)
        print()
        print()

    return(output)



async def determineCharacterAppearances(characterPassages, appearanceInstance: LMStudioSession):
    output = {}
    print(characterPassages['characters'])
    for character in characterPassages['characters']:
        print("character being analyzed for appearance: " + character)
        appearanceTemp = ""
        output[character] = {
            'name': character,
            'related passages': [],
            'direct passages': [],
            'appearance': ""
        }
        #generate list of passages tagged with character name
        passages = list(filter(lambda x: x['character list'] == character, characterPassages['tagged passages']))
        output[character]['direct passages'] = passages
        #collect all of the passages surrounding each mention of a given character throughout the entire text
        #also, iteratively generate a description of the mentioned character based on the accumulated description plus 
        #new passages
        for passage in passages:
            relatedPassages = collectSurroundingPassages(characterPassages, passage, 2, 3)
            output[character]['related passages'].append(relatedPassages)
            passageAreaText = list(functools.reduce(lambda x, y: x + "\n" + y['text'], relatedPassages, ""))
            appearanceData = "character name: " + character + "\ncurrent info\n" + appearanceTemp + "\nnew passages\n" + passageAreaText
            appearanceInstance.sendMessage(appearanceData)
            data = await appearanceInstance.receiveMessage()
            appearanceInstance.clearMessageHistory()
            appearanceTemp = decodeMessageContent(data)

        output[character]['appearance'] = appearanceTemp

    return(output)



def tokenCountEstimator(inputText): #based on a rough word count adjusted by a fixed multiplier
    output = len(inputText.split(" ")) * 1.3
    return(output)



def collectSurroundingPassages(dataSet, targetPassage, before, after):
    output = []
    index = targetPassage['index']
    lowerBound = max(0, index - before)
    lowHigherBound = min(index + 1, len(dataSet['tagged passages']))
    highHigherBound = min(index + (after + 1), len(dataSet['tagged passages']))
    previousSections = dataSet['tagged passages'][lowerBound:index]
    nextSections = dataSet['tagged passages'][lowHigherBound:highHigherBound]
    output = output.extend(previousSections)
    output.append(targetPassage)
    output.extend(nextSections)
    return(output)



def lineHasTerminator(inputLine: str):
    output = ("." in inputLine) or ("!" in inputLine) or ("?" in inputLine)
    return(output)



def sentenceFinder(inputLine: str, leftovers: str):
    buffer = inputLine
    output = ()
    sentences = []

    hasTerminator = lineHasTerminator(buffer)
    while(len(buffer) > 1):
        if(hasTerminator):
            markerPeriod = buffer.find(".") 
            markerExclamation = buffer.find("!")
            markerQuestion = buffer.find("?")
            collectedValues = [markerPeriod, markerExclamation, markerQuestion]
            clampedValues = list(map(lambda x: sys.maxsize if x == -1 else x, collectedValues))
            markerMin = min(clampedValues) + 1
            part = buffer[0:markerMin]
            buffer = buffer[markerMin:]
            sentence = leftovers + "\n" + part
            sentences.append(sentence)
            leftovers = ""
        else:
            leftovers = leftovers + "\n" + buffer
            buffer = ""
            
        hasTerminator = lineHasTerminator(buffer)
        

    output = (sentences, leftovers)
    return(output)



def chunkTextFile(inputFileName, sentenacesPerChunk):
    inputFile = open(inputFileName, "r")
    sentences = []
    chunks = []
    remainder = ""
    while(line := inputFile.readline()):
        line = line.strip()
        (buffer, remainder) = sentenceFinder(line, remainder)
        sentences.extend(buffer)
        
        chunk = ""
        while(len(sentences) > sentenacesPerChunk): 
            for x in range(sentenacesPerChunk):
                if(len(sentences) > 0):
                    chunk = chunk + str(sentences.pop(0))
            
            chunks.append(chunk)
            print(chunk)
            print("----------------------------------------------------------------------------")  

    while(len(sentences) > 0): #sensure the sentence buffer is empty before leaving.
            for x in range(2):
                if(len(sentences) > 0):
                    chunk = chunk + str(sentences.pop(0))
            
            chunks.append(chunk)
            print(chunk)
            print("----------------------------------------------------------------------------")  
    
    inputFile.close()
    return(chunks)



async def main(inputFileName, outputFileName):
    promptCharacterFinder = """[INST]name all of the people you see in passages i send you, please. send them to me as a numbered list.
                If you don't see the names of any people, respond with NAK.  If you understand, respond only with OK.[/INST]"""
    
    promptCharacterAppearance = """Given the name of a person, and a passage that they appear in, write a description of that person's appearance. 
                Format your response as a numbered list. Keep your descriptions simple and short. If you understand, respond only with OK.  Here 
                is an example;
                character name: Jane Doe
                passage: The young duo of Marvin and Jane made their way through the old house, slowly.  Due to her height, she frequently bumped her head on the low door ways.  Marvin, for once,
                was grateful for his shorter stature.  As they made their way into the dirty, damp basement, they found an old passage way, cut into the brick foundation of the 
                house.  It looked sturdy enough, but it was very narrow.  This time, it was Jane who was grateful.  Her slender figure allowed her to pass easily through the 
                narrow hallway, while Marvin was cursing his larger stomach, which was making it difficult to shimmy through.  Once on the other side, Jane's once long firey red hair 
                and Marvin's black hair was now brown and grey due to all of the dust and cobwebs.  

                output:
                young, tall, and slender, firey red hair."""
    
    promptNameChecker = """[INST]Tell me if the next message sent is the name of a person.  Repsond only with YES or NO.[/INST]"""
    
    print("preprocessing text data")
    chunks = chunkTextFile(inputFileName, 2) #reduced chunk size to 2 sentences.  testing indicates this could improve reliability of the character finder
    print("creating LM sessions")
    characterFinderSession = LMStudioSession("http://192.168.50.81:1234/v1/chat/completions", promptCharacterFinder)
    nameValidatorSession = LMStudioSession("http://192.168.50.81:1234/v1/chat/completions", promptNameChecker)
    characterAppearanceSession = LMStudioSession("http://192.168.50.81:1234/v1/chat/completions", promptCharacterAppearance)
    print("running character finder")
    characterData = await characterFinder(chunks, characterFinderSession, nameValidatorSession)
    print("running description creator")
    characterAppearances = await determineCharacterAppearances(characterData, characterAppearanceSession)

    print("writing out data to screen and file")
    print(characterData)
    outputFile = open(outputFileName, "w")
    outputFile.write(str(characterData))
    outputFile.write("\n\n")
    outputFile.write(str(characterAppearances))
    outputFile.close()



#main script
if(__name__ == '__main__'):
    inputFileName = sys.argv[1]
    outputFileName = sys.argv[2]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(inputFileName, outputFileName))
    



# curl http://localhost:1234/v1/chat/completions \
# -H "Content-Type: application/json" \
# -d '{ 
#   "messages": [ 
#     { "role": "system", "content": "Always answer in rhymes." },
#     { "role": "user", "content": "Introduce yourself." }
#   ], 
#   "temperature": 0.7, 
#   "max_tokens": -1,
#   "stream": false
# }'