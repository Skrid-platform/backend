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

    def __init__(self, p: list[Pitch] | None, duration: Duration, dots: int | None = 0, start: float | None = None, end: float | None = None, id_: str | None = None):
        '''
        Instantiates the class.

        In:
            - p: the list of pitches (only one if it is not a chord)
            - duration: the duration of the note (dots ignored here)
            - dots: the number of dots for the note
        '''

        if dots != None and dots < 0:
            raise ValueError('Chord: error: argument `dots` should be positive')
    
        self.pitches = p
        self.dur = duration
        self.dots = dots

        self.start = start
        self.end = end
        self.id = id_

    def get_duration_dots_float(self) -> float:
        '''Calculates the duration of the note, with the potential dots, and give the float representation.'''
    
        base_dur = self.dur.to_float()
        ret = base_dur

        # Add dots
        if self.dots != None:
            for k in range(self.dots):
                ret += base_dur / (k + 1)

        return ret

    def get_duration_dots_str(self) -> str:
        '''
        Calculates the duration of the note, with the potential dots, and give the string representation.
        If there are three dots, three 'd' will be added to the base duration represented as a string.
        '''
    
        dur = self.dur.to_str()

        if self.dots != None:
            dur += 'd'*self.dots

        return dur

    def is_silence(self) -> bool:
        '''Check if `self` represents a silence.'''
    
        if self.pitches == None:
            return False
        
        return self.pitches[0].class_ == 'r'

    def to_dict(self) -> dict[str, list[dict[str, None|str|int]] | int | float | None]:
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
            'id': self.id
        }

        return d

    def __repr__(self) -> str:
        '''
        Makes a user readable representation of a chord.

        Out:
            a string in the following format:
                `[note1, ...] dur_with_dots_str`, e.g `['c#/5', 'd/5'] hd`

                And if `start`, `end` or `id` is set:
                `[note1, ...] dur_with_dots_str start={start} end={end} id={id}`, e.g `['c#/5', 'd/5'] h start=0 end=0.5 id=azer`
        '''

        if self.pitches == None:
            return 'None'
    
        notes_repr = [str(p) for p in self.pitches]
        ret = f'{notes_repr} {self.get_duration_dots_str()}'

        if self.start != None and self.end != None:
            ret += f' start={self.start}, end={self.end}'

        if self.id != None:
            ret += f' id={self.id}'

        return ret

    def to_array_format(self, duration_format: str = 'int') -> tuple[list[str | None], int | str | float, int | None]:
        '''
        Makes an array representation of the pitches and durations, that is compatible with the cli parser format (see `utils.py/check_notes_input_format`)

        In:
            - duration_format: in ('int', 'str', 'float'). Used to select the format for duration. To be compatible with the parser format, use 'int' (default value).

        Out:
            a tuple of the following format:
                `([note1, ...], duration, dots)`
                E.g `(['c#/5'], 4, 0)`, or `(['a/4', 'd/5'], 16, 2)`
        '''
    
        if self.pitches == None:
            p = [None,]
    
        else:
            p = [str(p) for p in self.pitches]

        if duration_format == 'str':
            dur = self.dur.to_str()
        elif duration_format == 'float':
            dur = self.dur.to_float()
        else:
            dur = self.dur.to_int()

        dots = self.dots

        return (p, dur, dots)

