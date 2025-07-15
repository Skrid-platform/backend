#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Defines a CLI argument parser to interface the features'''

##-Imports
#---General
import argparse
import os
from os.path import exists

import neo4j

#---Project
from src.core.reformulation_V3 import reformulate_fuzzy_query
from src.core.process_results import (
    process_results_to_text,
    process_results_to_mp3,
    process_results_to_json,
    process_crisp_results_to_json
)
from src.db.neo4j_connection import connect_to_neo4j, run_query
from src.utils import (
    get_first_k_notes_of_each_score,
    create_query_from_list_of_notes,
    create_query_from_contour,
    check_notes_input_format,
    check_contour_input_format
)
from src.representation.chord import Chord, Duration, Pitch

#---Performance tests
def import_PerformanceLogger():
    global PerformanceLogger
    from tests.testing_utilities import PerformanceLogger

##-Init
# version = '1.0'
recording_to_notes_not_imported = True

NEO4J_DEFAULT_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_DEFAULT_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_DEFAULT_PWD = os.getenv("NEO4J_PASSWORD", "1234678")

##-Util
def import_recording_to_notes():
    '''
    Imports the module `recording_to_notes.py` if not already imported.
    Useful as it is long to load.
    '''

    global recording_to_notes_not_imported
    global RecordingToNotes

    if recording_to_notes_not_imported:
        from src.audio.recording_to_notes import RecordingToNotes
        recording_to_notes_not_imported = False

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

def get_notes_from_audio(fn: str, parser: argparse.ArgumentParser | None = None) -> list[Chord]:
    '''
    Convert the audio file `fn` to music notes using `recording_to_notes.py`.

    In:
        - fn: the path to the audio file
        - parser: used to raise the error with the current parser. Otherwise, raise an `argparse.ArgumentTypeError`.

    Out:
        the notes, in the format wanted by the `write` mode of the parser:
        `[[(class_1, octave_1), ..., (class_1n, octave_1n), duration_1, dots_1], ...]`
        E.g `"[[('c', 5), 1, 0], [('d', 5), ('f', 5), 4, 1]]"`
    '''

    import_recording_to_notes()

    try:
        C = RecordingToNotes()
        notes = C.get_notes(fn)

    except FileNotFoundError:
        if parser != None:
            parser.error(f'The file {fn} has not been found')
        else:
            raise argparse.ArgumentTypeError(f'The file {fn} has not been found')

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
            \twrite a fuzzy query       : python3 main_parser.py write \"[(['c#/5'], 4, 0), (['b/4'], 8, 1), (['a/4', 'd/5'], 16, 2)]\" -a 0.5 -t -o fuzzy_query.cypher
            \twrite a query from a song : python3 main_parser.py w \"$(python3 main_parser.py g \"10343_Avant_deux.mei\" 9)\" -p 2
            \tget notes from a song     : python3 main_parser.py get Air_n_83.mei 5 -o notes
            \tlist all songs            : python3 main_parser.py l
            \tlist all songs (compact)  : python3 main_parser.py l -n 0''',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        #---getenvAdd arguments
        # self.parser.add_argument(
        #     '-v', '--version',
        #     help='show version and exit',
        #     nargs=0,
        #     action=self.Version
        # )

        self.parser.add_argument(
            '-U', '--URI',
            default=NEO4J_DEFAULT_URI,
            help='the uri to the neo4j database'
        )
        self.parser.add_argument(
            '-u', '--user',
            default=NEO4J_DEFAULT_USER,
            help='the username to access the database'
        )
        self.parser.add_argument(
            '-p', '--password',
            default=NEO4J_DEFAULT_PWD,
            help='the password to access the database'
        )

        #------Sub-parsers
        self.subparsers = self.parser.add_subparsers(required=True, dest='subparser')

        self.create_compile();
        self.create_send();
        self.create_write();
        self.create_recording_convert();
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

    def clear_neo4j_cache(self):
        '''
        Clears the Neo4j cache.
        It creates the driver and closes it (using the authentification data given in argument)
        '''
    
        args = self.parser.parse_args()
        self.init_driver(args.URI, args.user, args.password)
        run_query(self.driver, "CALL db.clearQueryCaches()")
        self.close_driver()

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
            help="notes as a list of chords : [([note1, note2, ...], duration, dots), ...]. E.g \"[(['c#/5'], 4, 0), (['b/4'], 8, 1), (['b/4'], 8, 0), (['a/4', 'd/5'], 16, 2)]\""
        )

        self.parser_w.add_argument(
            '-F', '--file',
            action='store_true',
            help='NOTES is a file name (can be create with get mode)'
        )
        self.parser_w.add_argument(
            '-A', '--audio',
            action='store_true',
            help='NOTES is a file name of an audio file (can be create with get mode)'
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
            '-H', '--allow-homothety',
            action='store_true',
            help='Allow time homothety: match on duration ratio instead of duration'
        )
        self.parser_w.add_argument(
            '-io', '--incipit-only',
            action='store_true',
            help='Restrict the search to the start of musical scores'
        )
        self.parser_w.add_argument(
            '-C', '--contour-match',
            action='store_true',
            help='Match only the contour of the melody, i.e the general shape of melodic and rythmic intervals between notes'
        )

    def create_recording_convert(self):
        '''Creates the recording_convert subparser and add its arguments.'''

        #---Init
        self.parser_r = self.subparsers.add_parser('recording_convert', aliases=['r'], help='converts a recording to notes')

        #---Add arguments
        self.parser_r.add_argument(
            'AUDIO_FILE',
            help='path to the audio file'
        )

        self.parser_r.add_argument(
            '-o', '--output',
            help='give a filename where to write result. If not set, just print it.'
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

        elif args.subparser in ('r', 'recording_convert'):
            self.parse_recording_convert(args)

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

        res = reformulate_fuzzy_query(query)
        # try:
        #     res = reformulate_fuzzy_query(query)
        # except:
        #     print('parse_compile: error: query may not be correctly formulated')
        #     return

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
            print(f'parse_send: query syntax error: {err}')
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

        if args.file: # Read notes from a file
            notes_input = get_file_content(args.NOTES, self.parser_w)

        elif args.audio: # Convert notes from an audio
            notes_input_chords = get_notes_from_audio(args.NOTES, self.parser_w)
            notes_input_array = [c.to_array_format() for c in notes_input_chords]
            notes_input = str(notes_input_array)

        else:
            notes_input = args.NOTES
        
        # Validate notes input based on contour_match flag
        if args.contour_match: # Contour match mode: Validate that the input is in the correct dual-batch format
            contour = check_contour_input_format(notes_input)
            print(contour)
            query = create_query_from_contour(contour, args.incipit_only, args.collections)

        else: # Normal mode: Validate that the input is a list of notes
            try:
                notes = check_notes_input_format(notes_input)

            except (ValueError, SyntaxError):
                self.parser_w.error("NOTES must be a valid list format. Example: \"[(['c#/5'], 1), (['d/5', 'f/5'], 4, 1)]\"")

            query = create_query_from_list_of_notes(
                notes,
                args.pitch_distance,
                args.duration_factor,
                args.duration_gap,
                args.alpha,
                args.allow_transposition,
                args.allow_homothety,
                args.incipit_only,
                args.collections
            )

        if args.output == None:
            print(query)

        else:
            write_to_file(args.output, query)

    def parse_recording_convert(self, args):
        '''Parse the args for the recording_convert mode'''

        fn = args.AUDIO_FILE

        res = get_notes_from_audio(fn, self.parser_r)

        if args.output == None:
            print(res)

        else:
            write_to_file(args.output, res)

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
            self.close_driver()
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

        self.close_driver()


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

    try:
        if testing_mode:
            import_PerformanceLogger()
            logger = PerformanceLogger()

        app = Parser()
        app.parse()

        if testing_mode:
            logger.save()
            app.clear_neo4j_cache()
        
    except neo4j.exceptions.AuthError as err:
        print(f'Authentification error to the neo4j database: "{err}"')
        exit()

    except neo4j.exceptions.ServiceUnavailable as err:
        print(f'Connection error to the neo4j database: "{err}"')
        exit()

