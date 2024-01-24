this program can take in a large text file and perform the following tasks
1. find all of the named individuals in the text
2. generate physical descriptions of those individual based on the contents of the input text file
3. generate descriptions of those individuals personalities based on the contents of the input text file
4. output all of the gathered information as a structured json file

it requires an instance of LM studio with the server feature enabled running somewhere your machine has access to.  this substantially reduces the application complexity, and makes the process of changing the model being run quite trivial.  additionally, it means that you the operator have complete control and ownership of all of the infrastructure.

usage
python sentence-chunker.py <input.txt> <output.json> <IP address of machine running LM studio>
