class Note:
    def __init__(self, pitch, octave, duration, start=None, end=None, id_=None):
        self.pitch = pitch
        self.octave = octave
        self.duration = duration
        self.start = start
        self.end = end
        self.id = id_
    
    def __repr__(self):
        return (f"{self.pitch}{self.octave} {self.duration} start={self.start}")
