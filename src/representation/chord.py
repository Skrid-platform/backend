#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Represent a note or a chord: (list of pitches, duration, dots).'''

##-Import
from src.representation.pitch import Pitch
from src.representation.duration import Duration

##-Chord
class Chord:
    '''
    Represent a note or a chord: (list[Pitch], Duration, dots).
    A note is a chord with a single pitch.
    '''

    def __init__(self, p: list[Pitch] | None, duration: Duration, dots: int = 0, start: float | None = None, end: float | None = None, id_: str | None = None):
        '''
        Instantiates the class.

        In:
            - p: the list of pitches (only one if it is not a chord)
            - duration: the duration of the note (dots ignored here)
            - dots: the number of dots for the note
        '''

        if dots < 0:
            raise ValueError('Chord: error: argument `dots` should be positive')
    
        self.pitches = p
        self.dur = duration
        self.dots = dots

        self.start = start
        self.end = end
        self.id_ = id_

    def from_str(self, pitches):
        '''TODO: Docstring for from_str.

        In:
            - pitches: TODO
        Out:
            TODO
        '''
    
        pass #TODO: depends on the format given

    def get_duration_dots_float(self) -> float:
        '''Calculates the duration of the note, with the potential dots, and give the float representation.'''
    
        base_dur = self.dur.to_float()
        ret = base_dur

        # Add dots
        for k in range(self.dots):
            ret += base_dur / (k + 1)

        return ret

    def get_duration_dots_str(self) -> str:
        '''
        Calculates the duration of the note, with the potential dots, and give the string representation.
        If there are three dots, three 'd' will be added to the base duration represented as a string.
        '''
    
        base_dur = self.dur.to_str()
        return base_dur + 'd'*self.dots

    def to_dict(self) -> dict:
        '''
        Put all the relevant attributes into a dict.
        Used to convert to JSON.
        '''
    
        d = {
            'pitches': [p.to_dict() for p in self.pitches],
            'dur': self.dur.to_int(),
            'dots': self.dots,
            'start': self.start,
            'end': self.end,
            'id_': self.id_
        }

        return d

