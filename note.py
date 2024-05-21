class Note:
    def __init__(self, pitch, octave, duration, start, end):
        self.pitch = pitch
        self.octave = octave
        self.duration = duration
        self.start = start
        self.end = end
    
    def __repr__(self):
        return (f"Note(pitch={self.pitch}, octave={self.octave}, duration={self.duration}, "
                f"start={self.start}, end={self.end})")
