#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Represent the duration of a note in multiple formats'''

##-Duration
class Duration:
    '''Represent the duration of a note'''

    dur_str = ('w', 'h', 'q', '8', '16', '32')
    dur_int = (1, 2, 4, 8, 16, 32)
    dur_float = tuple([1 / k for k in dur_int])
    dur_float_dotted = tuple([k + k/2 for k in dur_float])

    def __init__(self, dur: int | str | float | None):
        '''
        Initiates the class.
        Tries to guess the correct type for the duration.

        In:
            - dur: the duration. Three possible representation are possible.

        String representation: in ('w', 'h', 'q', '8', '16', '32').
        Integer representation: in (1, 2, 4, 8, 16, 32). 
        Float representation: in (1, 1/2, 1/4, 1/8, 1/16, 1/32).

        The dots are not taken into account here.
        '''

        if dur is None:
            self.dur = None
            return

        if type(dur) == float:
            # Firstly, check if it is in fact an integer
            if dur in Duration.dur_int:
                self.from_int(dur)

            else:
                self.from_float(dur)

        elif type(dur) == int:
            self.from_int(dur)

        elif type(dur) == str:
            self.from_str(dur)

        else:
            raise ValueError('the type of `dur` is not in (int, str, float) !')

    def from_int(self, dur: int):
        '''
        Sets `self.dur` from an int value

        In:
            - dur: the duration, should be in `Duration.dur_int`.
        '''

        if dur not in Duration.dur_int:
            raise ValueError(f'Duration: from_int: error: value "{dur}" not in allowed values')

        self.dur = dur

    def from_str(self, dur: str):
        '''
        Sets `self.dur` from the string value (makes the conversion to int)

        In:
            - dur: the duration, should be in `Duration.dur_str`.
        '''

        if dur not in Duration.dur_str:
            raise ValueError(f'Duration: from_str: error: value "{dur}" not in allowed values')
    
        idx = Duration.dur_str.index(dur)
        self.dur = Duration.dur_int[idx]

    def from_float(self, dur: float | str):
        '''
        Sets `self.dur` from the float value (makes the conversion to int)

        In:
            - dur: the duration, should be in `Duration.dur_float`.
        '''

        # If the duration is the duration of a dotted note, remove the dotted duration (the attribute `dots` should be set somewhere else correctly).
        # Note that this will only work if dots = 1, but not for higher values.
        if dur in Duration.dur_float_dotted:
            dur = Duration.dur_float[Duration.dur_float_dotted.index(dur)]

        if dur not in Duration.dur_float:
            raise ValueError(f'Duration: from_float: error: value "{dur}" not in allowed values')
    
        idx = Duration.dur_float.index(dur)
        self.dur = Duration.dur_int[idx]

    def to_int(self) -> int:
        '''Returns the duration, represented as an integer.'''
    
        return self.dur

    def to_str(self) -> str:
        '''Returns the duration, represented as an string.'''
    
        idx = Duration.dur_int.index(self.dur)
        return Duration.dur_str[idx]

    def to_float(self) -> float:
        '''Returns the duration, represented as an float.'''
    
        idx = Duration.dur_int.index(self.dur)
        return Duration.dur_float[idx]

