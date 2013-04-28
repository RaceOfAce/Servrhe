from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from bs4 import UnicodeDammit
import json, random

class Markov(object):
    def __init__(self, db, aliases):
        self.db = db
        self.aliases = aliases
        self.users = {}
        self.ranking = {}
        self.loadUsers()
        LoopingCall(self.loadRanking).start(3600)

    @inlineCallbacks
    def loadUsers(self):
        result = yield self.db.runQuery("SELECT DISTINCT name FROM parts")
        for line in result:
            self.users[line[0]] = True

    @inlineCallbacks
    def loadRanking(self):
        result = yield self.db.runQuery("SELECT DISTINCT a.name, b.name_count FROM parts a INNER JOIN (SELECT name, COUNT(name) as name_count FROM parts GROUP BY name) b ON a.name = b.name ORDER BY b.name_count DESC")
        self.ranking = {}
        for rank, line in enumerate(result):
            name, lines = line
            self.ranking[name.lower()] = {
                "rank": rank+1,
                "name": name,
                "lines": lines
            }
    
    @inlineCallbacks
    def learn(self, name, phrase, channel):
        name = self.aliases.resolve(name)
        if name not in self.users:
            self.users[name] = True

        if "password" in phrase:
            return
        phrase = phrase.split(" ")
        phrase = filter(lambda x: x and "http" not in x and "ftp:" not in x and x[0] != ".", phrase)

        for i in range(len(phrase) + 1):
            seed = UnicodeDammit.detwingle(phrase[i-1] if i > 0 else "")
            answer = UnicodeDammit.detwingle(phrase[i] if i < len(phrase) else "")

            yield self.db.runQuery("INSERT INTO parts(name, seed, answer, source) VALUES(%s, %s, %s, %s)", (name, seed, answer, channel))

    @inlineCallbacks
    def ramble(self, name=None, seed=""):
        if name:
            name = self.aliases.resolve(name)
            if name not in self.users:
                returnValue("")

        message = []

        if seed:
            seed = UnicodeDammit.detwingle(seed)
            chunk = seed
            while chunk and len(" ".join(message)) < 300:
                message.append(chunk)
                chunk = yield self.prev(name, chunk)
            message.reverse()

        chunk = yield self.next(name, seed)
        while chunk and len(" ".join(message)) < 300:
            message.append(chunk)
            chunk = yield self.next(name, chunk)
            if not chunk and len(" ".join(message)) < 30:
                chunk = yield self.next(name, chunk)

        response = (" ".join(message)).decode("utf8")
        if seed and response == seed.decode("utf8"):
            response = yield self.ramble(name)
        returnValue(response)

    @inlineCallbacks
    def prev(self, name, seed):
        if name:
            result = yield self.db.runQuery('SELECT seed FROM parts WHERE name = %s AND answer = %s', (name, seed))
        else:
            result = yield self.db.runQuery('SELECT seed FROM parts WHERE answer = %s', (seed, ))
        if not result:
            returnValue("")
        row = random.randint(0, len(result) - 1)
        returnValue(result[row][0])

    @inlineCallbacks
    def next(self, name, seed):
        if name:
            result = yield self.db.runQuery("SELECT answer FROM parts WHERE name = %s AND seed = %s", (name, seed))
        else:
            result = yield self.db.runQuery("SELECT answer FROM parts WHERE seed = %s", (seed, ))
        if not result:
            returnValue("")
        row = random.randint(0, len(result) - 1)
        returnValue(result[row][0])
