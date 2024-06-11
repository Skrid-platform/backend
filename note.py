class Note:
    def __init__(self, pitch, octave, duration, start=None, end=None):
        self.pitch = pitch
        self.octave = octave
        self.duration = duration
        self.start = start
        self.end = end
    
    def __repr__(self):
        return (f"{self.pitch}{self.octave} {self.duration} start={self.start}")
