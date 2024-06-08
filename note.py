class Note:
    def __init__(self, pitch, octave, duration, start=None, end=None):
        self.pitch = pitch
        self.octave = octave
        self.duration = duration
        self.start = start
        self.end = end
    
    def __repr__(self):
        return (f"Note : {self.pitch}{self.octave}, duration={self.duration}, start={self.start}")
