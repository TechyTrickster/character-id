import requests
import asyncio



class LMStudioSession:
    def __init__(self, address, systemPrompt, timeout = 10, config = ""):
        self.address = address
        self.systemPrompt = systemPrompt
        self.chatHistory = []
        self.waitingForResponse = False
        self.messages = [self.generateSystemPromptLine(systemPrompt)]
        self.messageHandle = "empty"
        self.timeout = timeout
        self.config = {}

        if(config != ""):
            self.config = config
        else:
            self.config = {
                "temperature": 0.7, 
                "max_tokens": -1,
                "stream": False
            }
    

    def generateSystemPromptLine(self, prompt):
        output = {"role": "system", "content": prompt}
        return(output)
    
    
    def clearMessageHistory(self):
        self.messages = []
        prompt = self.generateSystemPromptLine(self.systemPrompt)
        self.messages.append(prompt)


    def sendMessage(self, message):
        self.waitingForResponse = True
        payload = {}
        payload.update(self.config)
        message = {"role": "user", "content": message}
        self.messages.append(message)
        payload['messages'] = self.messages
        print(payload)
        self.messageHandle = asyncio.create_task(self.sendMessageHelper(payload))
    

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
    

    async def sendMessageHelper(self, payload):
        output = requests.post(self.address, json = payload, timeout = self.timeout)
        return(output)
    

    def decodeMessageContent(self, data):
        output = data['choices'][0]['message']['content']
        return(output)