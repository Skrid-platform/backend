#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
#---General
import argparse
from os.path import exists
from ast import literal_eval # safer than eval

#---Project
from reformulation_V2 import reformulate_cypher_query
from neo4j_connection import connect_to_neo4j, run_query
from process_results import process_results_to_text, process_results_to_mp3
from utils import get_first_k_notes_of_each_score, create_query_from_list_of_notes

##-Init
# version = '1.0'

##-Util
def restricted_float(x, mn=0, mx=1):
    '''Defines a new type to restrict a float to the interval [mn ; mx].'''

    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'"{x}" is not a float')

    if x < mn or x > mx:
        raise argparse.ArgumentTypeError(f'"{x}" is not in range [{mn} ; {mx}]')

    return x

def get_file_content(fn):
    '''Try to read the file `fn`. Raise an argparse error if not found.'''
    try:
        with open(fn, 'r') as f:
            content = f.read()

    except FileNotFoundError:
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

def check_notes_input_format(notes_input):
    '''
    Ensure that `notes_input` is in the correct format : [(char, int, int), ...].
    If not, raise an argparse.ArgumentTypeError.

    Input :
        - notes_input : the user input (a string, not passed through literal_eval yet).

    Output :
        - a list of (char, int, int)  if the format is right ;
        - argparse.ArgumentTypeError  otherwise.
    '''

    format_notes = 'Notes format: triples list: [(class, octave, duration), ...]. E.g [(\'c\', 5, 1), (\'d\', 5, 4)]'

    try:
        notes = literal_eval(notes_input)

        for i, note in enumerate(notes):
            if type(note[0]) != str or len(note[0]) != 1:
                raise argparse.ArgumentTypeError(f'error with note {i}: "{note[0]}" is not a class.\n' + format_notes)

            if type(note[1]) != int:
                raise argparse.ArgumentTypeError(f'error with note {i}: "{note[1]}" is not an int\n' + format_notes)

            if type(note[2]) != int:
                raise argparse.ArgumentTypeError(f'error with note {i}: "{note[2]}" is not an int\n' + format_notes)

    except Exception:
        raise argparse.ArgumentTypeError('The input notes are not in the correct format !\n' + format_notes)

    return notes

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
            #TODO: Add examples !
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
            '-o', '--output',
            help='give a filename where to write result. The extension has to be ".txt" (in which case the result is saved as text) or ".mp3" (in which case the result is saved as mp3). If omitted, the json is printed to stdout.'
        )
        self.parser_s.add_argument(
            '-m', '--max-files',
            type=int,
            default=1,
            help='the maximum number of files when storing .mp3. Default : 1.'
        )

    def create_write(self):
        '''Creates the write subparser and add its arguments.'''

        #---Init
        self.parser_w = self.subparsers.add_parser('write', aliases=['w'], help='write a fuzzy query')

        #---Add arguments
        self.parser_w.add_argument(
            'NOTES',
            help='notes as triples list : [(class, octave, duration), ...]. E.g [(\'c\', 5, 1), (\'d\', 5, 4)]'
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
            type=float, #TODO: make a better type as restricted_float
            help='the pitch distance. Default is 0.0' #TODO: make a better help
        )
        self.parser_w.add_argument(
            '-f', '--duration-factor',
            default=1.0,
            type=float, #TODO: make a better type as restricted_float
            help='the duration factor. Default is 1.0' #TODO: make a better help
        )
        self.parser_w.add_argument(
            '-g', '--duration-gap',
            default=0.0,
            type=float, #TODO: make a better type as restricted_float
            help='the duration gap. Default is 0.0' #TODO: make a better help
        )
        self.parser_w.add_argument(
            '-a', '--alpha',
            default=0.0,
            type=restricted_float,
            help='the alpha setting. In range [0 ; 1]. Remove every result that has a score below alpha. Default is 0.0' #TODO: make a better help
        )
        self.parser_w.add_argument(
            '-t', '--allow-transposition',
            action='store_true',
            help='Allow transposition' #TODO: make a better help
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
            self.parse_send(args)

        elif args.subparser in ('w', 'write'):
            self.parse_write(args)

        elif args.subparser in ('g', 'get'):
            self.parse_get(args)

        elif args.subparser in ('l', 'list'):
            self.parse_list(args)

    def parse_compile(self, args):
        '''Parse the args for the compile mode'''

        if args.file:
            query = get_file_content(args.QUERY)
        else:
            query = args.QUERY

        res = reformulate_cypher_query(query)

        if args.output == None:
            print(res)

        else:
            write_to_file(args.output, res)

    def parse_send(self, args):
        '''Parse the args for the send mode'''

        if args.file:
            query = get_file_content(args.QUERY)
        else:
            query = args.QUERY

        if args.fuzzy:
            query = reformulate_cypher_query(query)

        self.init_driver(args.URI, args.user, args.password)
        res = run_query(self.driver, query)

        if args.output == None:
            print(res)

        else:
            if args.output[-4:] == '.txt':
                # write_to_file(args.output, res)
                process_results_to_text(res, query, args.output)

            elif args.output[-4:] == '.mp3':
                process_results_to_mp3(res, query, args.max_files, self.driver)

    def parse_write(self, args):
        '''Parse the args for the write mode'''

        if args.file:
            notes_input = get_file_content(args.NOTES)
        else:
            notes_input = args.NOTES

        notes = check_notes_input_format(notes_input)
        query = create_query_from_list_of_notes(notes, args.pitch_distance, args.duration_factor, args.duration_gap, args.alpha, args.allow_transposition)

        if args.output == None:
            print(query)
        else:
            write_to_file(args.output, query)

    def parse_get(self, args):
        '''Parse the args for the get mode'''

        self.init_driver(args.URI, args.user, args.password)

        #TODO: check that args.NAME is in the list ...

        res = get_first_k_notes_of_each_score(args.NUMBER, args.NAME, self.driver)

        if args.output == None:
            print(res)
        else:
            write_to_file(args.output, res)

    def parse_list(self, args):
        '''Parse the args for the list mode'''

        self.init_driver(args.URI, args.user, args.password)

        query = "MATCH (s:Score) RETURN DISTINCT s.source AS source"
        result = run_query(self.driver, query)

        res = ''
        for record in result:
            res += record['source'] + '\n'

        if args.output == None:
            print(res)
        else:
            write_to_file(args.output, res)


    # class Version(argparse.Action):
    #     '''Class used to show Synk version.'''
    #
    #     def __call__(self, parser, namespace, values, option_string):
    #
    #         print(f'v{version}')
    #         parser.exit()


##-Run
if __name__ == '__main__':
    app = Parser()
    app.parse()
