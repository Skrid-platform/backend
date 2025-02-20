#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
#---General
import argparse
from os.path import exists
from ast import literal_eval # safer than eval
import re

# import neo4j.exceptions.CypherSyntaxError
import neo4j

#---Project
from reformulation_V3 import reformulate_fuzzy_query
from neo4j_connection import connect_to_neo4j, run_query
from process_results import process_results_to_text, process_results_to_mp3, process_results_to_json, process_crisp_results_to_json
from utils import get_first_k_notes_of_each_score, create_query_from_list_of_notes, create_query_from_contour

#---Performance tests
from testing_utilities import PerformanceLogger

##-Init
# version = '1.0'

##-Util
def restricted_float(x, mn=None, mx=None):
    '''
    Defines a new type to restrict a float to the interval [mn ; mx].

    If mn is None, it acts the same as -inf.
    If mx is None, it acts the same as +inf.
    '''

    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'"{x}" is not a float')

    if mn != None and x < mn:
        if mx == None:
            mx = '+inf'

        raise argparse.ArgumentTypeError(f'"{x}" is not in range [{mn} ; {mx}] (x < {mn})')

    elif mx != None and x > mx:
        if mn == None:
            mn = '-inf'

        raise argparse.ArgumentTypeError(f'"{x}" is not in range [{mn} ; {mx}] (x > {mx})')

    return x

def semi_int(x):
    r'''Defines a new type : \N / 2 (int or half an int).'''

    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'"{x}" is not a float')

    is_int = lambda x : int(x) == x

    if not (is_int(x) or is_int(2 * x)):
        raise argparse.ArgumentTypeError(f'"{x}" is not an integer or half an integer')

    return x

def get_file_content(fn, parser=None):
    '''
    Try to read the file `fn`.
    If not found and `parser` != None, raise an error with `parser.error`. If `parser` is None, raise an `ArgumentTypeError`.
    '''
    try:
        with open(fn, 'r') as f:
            content = f.read()

    except FileNotFoundError:
        if parser != None:
            parser.error(f'The file {fn} has not been found')
        else:
            raise argparse.ArgumentTypeError(f'The file {fn} has not been found')

    return content

def write_to_file(fn, content):
    '''Write `content` to file `fn`'''

    if exists(fn):
        if input(f'File "{fn}" already exists. Overwrite (y/n) ?\n>').lower() not in ('y', 'yes', 'oui', 'o'):
            print('Aborted.')
            return

    with open(fn, 'w') as f:
        f.write(content)

def check_notes_input_format(notes_input: str) -> list[list[tuple[str|None, int|None] | int|float|None]]:
    '''
    Ensure that `notes_input` is in the correct format (see below for a description of the format).
    If not, raise an argparse.ArgumentTypeError.

    Input :
        - notes_input : the user input (a string, not a list).

    Output :
        - a list of (char, int, int)  if the format is right ;
        - argparse.ArgumentTypeError  otherwise.

    Description for the format of `notes` :
        `notes` should be a list of `note`s.
        A `note` is a list of the following format : `[(class_1, octave_1), ..., (class_n, octave_n), duration, dots (optional)]`

        For example : `[[('c', 5), 4, 0], [('b', 4), 8, 1], [('b', 4), 8], [('a', 4), ('d', 5), 16, 2]]`.

        duration is in the following format: 1 for whole, 2 for half, ...
        dots is an optional integer representing the number of dots.
    '''

    #---Init (functions to test each part)
    def check_class(class_: str|None) -> bool:
        '''Return True iff `class_` is in correct format.'''

        return (
            class_ == None
            or (
                isinstance(class_, str)
                and (
                    len(class_) == 1 or
                    (len(class_) == 2 and class_[1] in '#sbf')
                )
                and
                class_[0] in 'abcdefgr'
            )
        )

    def check_octave(octave: int|None) -> bool:
        '''Return True iff `octave` is in correct format.'''

        return isinstance(octave, (int, type(None)))

    def check_duration(duration: int|float|None) -> bool:
        '''Return True iff `duration` is in correct format.'''

        return isinstance(duration, (int, float, type(None)))

    def check_dots(dots: int|None) -> bool:
        '''Return True iff `dots` is in correct format.'''

        return isinstance(dots, (int, type(None))) and (dots is None or dots >= 0)

    format_notes = "Notes format: list of [(class, octave), duration, dots]: [[(class, octave), ..., duration, dots], ...]. E.g `[[(\'c\', 5), 4, 0], [(\'b\', 4), 8, 1], [(\'b\', 4), 8], [(\'a\', 4), (\'d\', 5), 16, 2]]`. It is possible to use \"None\" to ignore a criteria. Dots are optinal, with default value of 0."

    #---Convert string to list
    notes_input = notes_input.replace("\\", "")
    notes = literal_eval(notes_input)

    #---Check
    for i, note_or_chord in enumerate(notes):
        #-Check type of the current note/chord (e.g [('c', 5), 8])
        if type(note_or_chord) != list:
            raise argparse.ArgumentTypeError(f'error with note {i}: should be a a list, but "{note_or_chord}", of type {type(note_or_chord)} found !\n' + format_notes)

        #-Check the length of the current note/chord (e.g [('c', 5), 8])
        if len(note_or_chord) < 2:
            raise argparse.ArgumentTypeError(f'error with note {i}: there should be at least two elements in the list, for example `[(\'c\', 5), 4]`, but "{note_or_chord}", with length {len(note_or_chord)} found !\n' + format_notes)

        #-Check the duration
        duration = note_or_chord[1]
        if not check_duration(duration):
            raise argparse.ArgumentTypeError(f'error with note {i}: "{note_or_chord}": "{duration}" (duration) is not a float (or None)\n' + format_notes)

        #-Check the dots (if provided)
        if len(note_or_chord) > 2:
            dots = note_or_chord[-1]
            if not check_dots(dots):
                raise argparse.ArgumentTypeError(f'error with note {i}: "{note_or_chord}": "{dots}" (dots) is not a non-negative integer or None\n' + format_notes)
        else:
            dots = 0  # Default to 0 if dots are not provided

        #-Check each note
        for j, note in enumerate(note_or_chord[:-2]):
            #-Check type of note tuple
            if type(note) != tuple:
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: should be a tuple (e.g `(\'c\', 5)`), but "{note}", of type {type(note)} found !\n' + format_notes)

            #-Check length of note tuple
            if len(note) != 2:
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: note tuple should have 2 elements (class, octave), but {len(note_or_chord)} found !\n' + format_notes)

            #-Check note class
            if not check_class(note[0]):
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: "{note}": "{note[0]}" is not a note class.\n' + format_notes)

            #-Check note octave
            if not check_octave(note[1]):
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: "{note}": "{note[1]}" (octave) is not an int, or a float, or None.\n' + format_notes)

    return notes



def list_available_songs(driver, collection=None):
    '''
    Return a list of all the available songs.

    - driver     : the neo4j connection driver ;
    - collection : List only scores for the given collection. If `None`, list for all.
    '''

    if collection == None:
        query = 'MATCH (s:Score) RETURN DISTINCT s.source AS source'
    else:
        query = f'MATCH (s:Score) WHERE s.collection CONTAINS "{collection}" RETURN DISTINCT s.source AS source'

    result = run_query(driver, query)

    return [record['source'] for record in result]

##-Parser
class Parser:
    '''Defines an argument parser'''

    def __init__(self):
        '''Initiate Parser'''

        #------Main parser
        #---Init
        self.parser = argparse.ArgumentParser(
            # prog='UnfuzzyQuery',
            description='Compiles fuzzy queries to cypher queries',
            # epilog='Examples :\n\tSearchWord word\n\tSearchWord "example of string" -e .py;.txt\n\tSearchWord someword -x .pyc -sn',
            epilog='''Examples :
            \tget help on a subcommand  : python3 main_parser.py compile -h
            \tcompile a query from file : python3 main_parser.py compile -F fuzzy_query.cypher -o crisp_query.cypher
            \tsend a query              : python3 main_parser.py send -F crisp_query.cypher -t result.txt
            \tsend a query 2            : python3 main_parser.py -u user -p pwd send -F -f fuzzy_query.cypher -t result.txt -m 6
            \twrite a fuzzy query       : python3 main_parser.py write \"[[('c', 5), 1, 1], [('d', 5), None]]\" -a 0.5 -t -o fuzzy_query.cypher
            \twrite a query from file   : python3 main_parser.py w \"$(python3 main_parser.py g \"10343_Avant_deux.mei\" 9)\" -p 2
            \tget notes from a song     : python3 main_parser.py get Air_n_83.mei 5 -o notes
            \tlist all songs            : python3 main_parser.py l
            \tlist all songs (compact)  : python3 main_parser.py l -n 0''',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        #---Add arguments
        # self.parser.add_argument(
        #     '-v', '--version',
        #     help='show version and exit',
        #     nargs=0,
        #     action=self.Version
        # )

        self.parser.add_argument(
            '-U', '--URI',
            default='bolt://localhost:7687',
            help='the uri to the neo4j database'
        )
        self.parser.add_argument(
            '-u', '--user',
            default='neo4j',
            help='the username to access the database'
        )
        self.parser.add_argument(
            '-p', '--password',
            default='12345678',
            help='the password to access the database'
        )

        #------Sub-parsers
        self.subparsers = self.parser.add_subparsers(required=True, dest='subparser')

        self.create_compile();
        self.create_send();
        self.create_write();
        self.create_get();
        self.create_list();

    def init_driver(self, uri, user, password):
        '''
        Creates self.driver.

        - uri      : the uri of the database ;
        - user     : the username to access the database ;
        - password : the password to access the database.
        '''

        self.driver = connect_to_neo4j(uri, user, password)

    def close_driver(self):
        '''Closes the driver'''

        self.driver.close()


    def create_compile(self):
        '''Creates the compile subparser and add its arguments.'''

        #---Init
        self.parser_c = self.subparsers.add_parser('compile', aliases=['c'], help='compile a fuzzy query to a valid cypher one')

        #---Add arguments
        self.parser_c.add_argument(
            'QUERY',
            help='the fuzzy query to convert (string, or filename if -F is used).'
        )

        self.parser_c.add_argument(
            '-F', '--file',
            action='store_true',
            help='if used, QUERY will be considered as a file name and not a raw query.'
        )
        self.parser_c.add_argument(
            '-o', '--output',
            help='give a filename where to write result. If not set, just print it.'
        )

    def create_send(self):
        '''Creates the send subparser and add its arguments.'''

        #---Init
        self.parser_s = self.subparsers.add_parser('send', aliases=['s'], help='send a query and return the result')

        #---Add arguments
        self.parser_s.add_argument(
            'QUERY',
            help='the query to convert (string, or filename if -F is used)'
        )

        self.parser_s.add_argument(
            '-F', '--file',
            action='store_true',
            help='if used, QUERY will be considered as a file name and not a raw query.'
        )
        self.parser_s.add_argument(
            '-f', '--fuzzy',
            action='store_true',
            help='the query is a fuzzy one. Convert it before sending it.'
        )
        self.parser_s.add_argument(
            '-j', '--json',
            action='store_true',
            help='display the result in json format.'
        )
        self.parser_s.add_argument(
            '-t', '--text-output',
            help='save the result as text in the file TEXT_OUTPUT'
        )
        self.parser_s.add_argument(
            '-m', '--mp3',
            type=int,
            help='save the result as mp3 files. MP3 is the maximum number of files to write.'
        )

    def create_write(self):
        '''Creates the write subparser and add its arguments.'''

        #---Init
        self.parser_w = self.subparsers.add_parser('write', aliases=['w'], help='write a fuzzy query')

        #---Add arguments
        self.parser_w.add_argument(
            'NOTES',
            # type=check_notes_input_format,
            help='notes as a list of lists : [[(class_1, octave_1), duration_1, dots_1], [(class_2, octave_2), duration_2, dots_2], ...]. E.g \"[[(\'c\', 5), 1, 0], [(\'d\', 5), 4, 1]]\"'
        )

        self.parser_w.add_argument(
            '-F', '--file',
            action='store_true',
            help='NOTES is a file name (can be create with get mode)'
        )
        self.parser_w.add_argument(
            '-o', '--output',
            help='give a filename where to write result. If omitted, it is printed to stdout.'
        )

        self.parser_w.add_argument(
            '-p', '--pitch-distance',
            default=0.0,
            type=semi_int,
            help='the pitch distance fuzzy parameter (in tones). Default is 0.0 (exact match). A pitch distance of `d` means that it is possible to match a note distant of `d` tones from the search note.'
        )
        self.parser_w.add_argument(
            '-f', '--duration-factor',
            default=1.0,
            type=lambda x: restricted_float(x, 0, None),
            help='the duration factor fuzzy parameter (multiplicative factor). Default is 1.0. A duration factor of `f` means that it is possible to match notes with a duration between `d` and `f * d` (if `d` is the duration of the searched note).'
        )
        self.parser_w.add_argument(
            '-g', '--duration-gap',
            default=0.0,
            type=lambda x: restricted_float(x, 0, None),
            help='the duration gap fuzzy parameter (in proportion of a whole note, e.g 0.25 for a quarter note). Default is 0.0. A duration gap of `g` means that it is possible to match the pattern by adding notes of duration `g` between the searched notes.'
        )
        self.parser_w.add_argument(
            '-a', '--alpha',
            default=0.0,
            type=lambda x: restricted_float(x, 0, 1),
            help='the alpha setting. In range [0 ; 1]. Remove every result that has a score below alpha. Default is 0.0'
        )
        self.parser_w.add_argument(
            '-c', '--collections',
            help='filter by collections. Separate values with commas, without space, e.g: -c "col 1","col 2","col 3"'
        )
        self.parser_w.add_argument(
            '-t', '--allow-transposition',
            action='store_true',
            help='Allow pitch transposition: match on note interval instead of pitch'
        )
        self.parser_w.add_argument(
            '-C', '--contour-match',
            action='store_true',
            help='Match only the contour of the melody, i.e the general shape of melodic and rythmic intervals between notes'
        )

    def create_get(self):
        '''Creates the get subparser and add its arguments.'''

        #---Init
        self.parser_g = self.subparsers.add_parser('get', aliases=['g'], help='get the k first notes of a song')

        #---Add arguments
        self.parser_g.add_argument(
            'NAME',
            help='the name of the song. Use the list mode to list them all.'
        )
        self.parser_g.add_argument(
            'NUMBER',
            type=int,
            help='the number of notes to get from the song.'
        )

        self.parser_g.add_argument(
            '-o', '--output',
            help='the filename where to write the result. If omitted, print it to stdout.'
        )

    def create_list(self):
        '''Creates the list subparser and add its arguments.'''

        #---Init
        self.parser_l = self.subparsers.add_parser('list', aliases=['l'], help='list the available songs')

        #---Add arguments
        self.parser_l.add_argument(
            '-c', '--collection',
            help='Filter scores by collection name'
        )
        self.parser_l.add_argument(
            '-n', '--number-per-line',
            type=int,
            help='Show NUMBER_PER_LINE songs instead of one. With -n 0, display all on the same line.'
        )
        self.parser_l.add_argument(
            '-o', '--output',
            help='the filename where to write the result. If omitted, print it to stdout.'
        )


    def parse(self):
        '''Parse the args'''

        #---Get arguments
        args = self.parser.parse_args()
        # print(args)

        #---Redirect towards the right method
        if args.subparser in ('c', 'compile'):
            self.parse_compile(args)

        elif args.subparser in ('s', 'send'):
            if testing_mode:
                logger.start("w_comp_and_ranking")
            self.parse_send(args)
            if testing_mode:
                logger.end("w_comp_and_ranking")

        elif args.subparser in ('w', 'write'):
            self.parse_write(args)

        elif args.subparser in ('g', 'get'):
            self.parse_get(args)

        elif args.subparser in ('l', 'list'):
            self.parse_list(args)

    def parse_compile(self, args):
        '''Parse the args for the compile mode'''

        if args.file:
            query = get_file_content(args.QUERY, self.parser_c)
        else:
            query = args.QUERY

        try:
            res = reformulate_fuzzy_query(query)
        except:
            print('parse_compile: error: query may not be correctly formulated')
            return

        if args.output == None:
            print(res)

        else:
            write_to_file(args.output, res)

    def parse_send(self, args):
        '''Parse the args for the send mode'''

        if args.file:
            query = get_file_content(args.QUERY, self.parser_s)
        else:
            query = args.QUERY

        if args.fuzzy:
            try:
                crisp_query = reformulate_fuzzy_query(query)
            except:
                print('parse_send: compile query: error: query may not be correctly written')
                return

        else:
            crisp_query = query

        self.init_driver(args.URI, args.user, args.password)

        try:
            if testing_mode:
                logger.start("only_query")
            res = run_query(self.driver, crisp_query)
            if testing_mode:
                logger.end("only_query")
        except neo4j.exceptions.CypherSyntaxError as err:
            print('parse_send: query syntax error: ' + str(err))
            return

        if args.text_output == None and args.mp3 == None:
            if args.fuzzy:
                if args.json:
                    print(process_results_to_json(res, query))
                else:
                    print(process_results_to_text(res, query))

            else:
                if args.json:
                    print(process_crisp_results_to_json(res))
                else:
                    for k in res:
                        print(k)

        else:
            if args.text_output != None:
                if not args.fuzzy:
                    print(res)
                    self.parser_s.error('Can only process result to text if the query is fuzzy !\nThe result has been printed above.')

                processed_res = process_results_to_text(res, query)
                write_to_file(args.text_output, processed_res)

            if args.mp3 != None:
                process_results_to_mp3(res, query, args.mp3, self.driver)

        self.close_driver()

    def parse_write(self, args):
        '''Parse the args for the write mode'''

        if args.allow_transposition and args.contour_match:
            self.parser_w.error('not possible to use `-t` and `-C` at the same time')

        if args.file:
            notes_input = get_file_content(args.NOTES, self.parser_w)
        else:
            notes_input = args.NOTES

        if args.collections == None:
            collections = None
        else:

            collections = args.collections
        
        # Validate notes input based on contour_match flag
        if args.contour_match:
            # Contour match mode: Validate that the input is in the correct alternating format
            pattern = r'^(([LSMX]|\*?[UDRudX])(-([LSMX]|\*?[UDRudX]))*)$'
            if not re.match(pattern, notes_input):
                self.parser_w.error("When using `-C`, NOTES must be a string containing rhythmic symbols ('L', 'M', 'S', 'X') and melodic contour symbols ('*U', 'U', 'u', 'R', 'd', 'D', '*D', 'X'), separated by '-'. Example: 'L-X-M-d-S'.")

            # Split the input into components
            contour_elements = notes_input.split('-')
            # Separate 'X' for interval (changed to 'x') and for note duration 
            contour_elements = ['x' if i % 2 == 1 and element == 'X' else element for (i, element) in enumerate(contour_elements)]

            # Separate rhythmic and melodic contours
            rhythmic_contours = []
            melodic_contours = []

            for element in contour_elements:
                if re.match(r'^[LSMX]$', element):
                    rhythmic_contours.append(element)
                elif re.match(r'^\*?[UDRudx]$', element):
                    melodic_contours.append(element)
                else:
                    self.parser_w.error(f"Invalid contour element: '{element}'.")

            # Ensure there are n rhythmic symbols for n-1 melodic symbols
            if len(rhythmic_contours) != len(melodic_contours) + 1:
                self.parser_w.error("The contour format requires n rhythmic symbols for n-1 melodic contour symbols. Example: 'L-d-M-R-S'.")

            contour = {
                'rhythmic': rhythmic_contours,
                'melodic': melodic_contours
            }

            query = create_query_from_contour(contour)
        else:
            # Normal mode: Validate that the input is a list of notes
            try:
                notes = check_notes_input_format(notes_input)
            except (ValueError, SyntaxError):
                self.parser_w.error("NOTES must be a valid list format. Example: \"[[(\'c\', 5), 1], [(\'d\', 5), 4, 1]]\"")
            query = create_query_from_list_of_notes(notes, args.pitch_distance, args.duration_factor, args.duration_gap, args.alpha, args.allow_transposition, args.contour_match, collections)

        if args.output == None:
            print(query)
        else:
            write_to_file(args.output, query)

    def parse_get(self, args):
        '''Parse the args for the get mode'''

        self.init_driver(args.URI, args.user, args.password)

        if args.NAME not in list_available_songs(self.driver):
            self.close_driver()
            self.parser_g.error(f'NAME argument ("{args.NAME}") is not valid (check valid songs with `python3 main_parser.py list`)')

        res = get_first_k_notes_of_each_score(args.NUMBER, args.NAME, self.driver)

        if args.output == None:
            print(res)
        else:
            write_to_file(args.output, res)

        self.close_driver()

    def parse_list(self, args):
        '''Parse the args for the list mode'''

        self.init_driver(args.URI, args.user, args.password)

        if args.number_per_line != None and args.number_per_line < 0:
            self.close_driver();
            self.parser_l.error('argument `-n` takes a positive value !')

        songs = list_available_songs(self.driver, args.collection)

        res = ''
        for i, song in enumerate(songs):
            res += song

            if args.number_per_line == 0:
                res += ', '
            elif args.number_per_line == None or i % args.number_per_line == 0:
                res += '\n'
            else:
                res += ', '

        res = res.strip('\n')

        if args.output == None:
            print(res)
        else:
            write_to_file(args.output, res)

        self.close_driver();


    # class Version(argparse.Action):
    #     '''Class used to show Synk version.'''
    #
    #     def __call__(self, parser, namespace, values, option_string):
    #
    #         print(f'v{version}')
    #         parser.exit()


##-Run
if __name__ == '__main__':
    testing_mode = False

    if testing_mode:
        logger = PerformanceLogger()
        app = Parser()
        app.parse()
        logger.save()

        # Set up a driver just to clear the cache
        uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
        user = "neo4j"                 # Default username
        password = "12345678"          # Replace with your actual password
        driver = connect_to_neo4j(uri, user, password)
        run_query(driver, "CALL db.clearQueryCaches()")
    
    else:
        app = Parser()
        app.parse()
