import Card


class Player:
    def __init__(self, name, chips):
        self.name = name
        self.chips = chips
        self.hand: list[Card] = []
        self.currentBet = 0
        self.folded = False
        self.allIn = False

    def getName(self):
        return self.name

    def setName(self, value):
        self.name = value

    def getChips(self):
        return self.chips

    def setChips(self, value):
        self.chips = value

    def getHand(self):
        return self.hand

    def setHand(self, value):
        self.hand = value

    def getCurrentBet(self):
        return self.currentBet

    def setCurrentBet(self, value):
        self.currentBet = value

    def isFolded(self):
        return self.folded

    def setFolded(self, value):
        self.folded = value

    def isAllIn(self):
        return self.allIn

    def setAllIn(self, value):
        self.allIn = value
