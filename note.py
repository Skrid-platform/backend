class Note:
    def __init__(self, pitch, octave, dur, dots=None, duration=None, start=None, end=None, id_=None):
        self.pitch = pitch
        self.octave = octave
        self.dur = dur
        if dots is None and duration is None:
            self.duration = 1.0/dur
        elif duration is None:
            self.duration = 1.0/dur*1.5
        else:
            self.duration = duration
        self.dots = dots
        self.start = start
        self.end = end
        self.id = id_
    
    def to_list(self):
        if self.dots is not None and self.dots > 0:
            return [(self.pitch, self.octave), self.dur, self.dots]
        else:
            return [(self.pitch, self.octave), self.dur]

    def __repr__(self):
        if self.dots == 0 or self.dots is None:
            return (f"{self.pitch}{self.octave} {self.dur} start={self.start}")
        else:
            return (f"{self.pitch}{self.octave} dotted {self.dur} start={self.start}")
