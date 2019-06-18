import json
import pprint
import requests
from bs4 import BeautifulSoup
from argparse import ArgumentParser


def parse_args():
    description = 'Parses Belarus State Economic University\'s staff list.'
    arg_parser = ArgumentParser(description=description)
    arg_parser.add_argument('-f', '--file',
        type=str, dest='file_path', default=False,
        help='output results to passed file path')
    arg_parser.add_argument('-q', '--quiet',
        action='store_true', dest='silent_mode', default=False,
        help='suppress all logs')
    arg_parser.add_argument('-v', '--verbose',
        action='store_true', dest='verbose_mode', default=False,
        help='output all values, has an effect if -q or --quiet is not set')
    arg_parser.add_argument('--pretty',
        action='store_true', dest='pretty_output', default=False,
        help='pretty output to console and/or files')
    return arg_parser.parse_args()


def main():
    args = parse_args()

    bseu_parser = Parser(options=vars(args))
    bseu_parser.run()


def get_html_parser(url):
    """Makes a GET request and returns BeautifulSoup object as a result"""
    response = requests.get(url)
    return BeautifulSoup(response.content, 'html.parser')


# Parsers
# Work with BeautifulSoup and extract the necessary data

def parse_staff_links(soup, div_id):
    """Returns list of urls of personal pages"""
    soup = soup.find('div', {'id': div_id})
    links = []
    for a in soup.find_all('a', href=True):
        links.append(a['href'])
    return links


def parse_degree_(soup):
    degree_string= soup.find('p', {'class': 'noIndnt'}).br.next_sibling
    return degree_string.partition(u'\xa0')[0]


def parse_personal_page(soup, div_id):
    soup = soup.find('div', {'id': div_id})
    if soup.img:
        img = soup.img['src']
    else:
        img = ''
    full_name = soup.h4.text
    degree_string = parse_degree_(soup)
    return full_name, img, degree_string


# Transformers
# Convert parsed data to proper format

def transform_full_name(full_name):
    names = full_name.split()
    if len(names) == 2:
        names.append('')
    else:
        names = [names[0], names[1], ' '.join(names[2:])]
    return {
        'last_name': names[0],
        'first_name': names[1],
        'middle_name': names[2],
    }


def transform_degree(degree_string):
    degrees = [
        'преподаватель',
        'старший преподаватель',
        'доцент',
        'профессор',
        'ассистент',
    ]
    if degree_string.lower() in degrees:
        return degrees.index(degree_string.lower())
    else:
        return len(degrees)


class Parser:
    """Stores global configuration and a few options"""
    base_url = 'http://www.bseu.by/PersonalPages/alphabetic.htm'
    personal_page_prefix = 'http://www.bseu.by'
    staff_div_id = 'Pages'
    person_div_id = 'persinfo'
    default_image = 'https://mytimetable.live/images/man-user.png'

    def __init__(self, base_url=None, options={}):
        self.base_url = base_url or Parser.base_url
        self.options = {
            'silent_mode': False,
            'verbose_mode': False,
            'pretty_output': False,
            'file_path': None,
        }
        self.options.update(options)

    def log_data(self, data, **kwargs):
        output = ''
        if self.options['pretty_output']:
            pp = pprint.PrettyPrinter(indent=2)
            output = pp.pformat(data)
        else:
            output = str(data)
        print(output, **kwargs)

    def log(self, message = '', output = None, **kwargs):
        if not self.options['silent_mode']:
            if not output:
                print(message)
                return
            if self.options['verbose_mode']:
                print(message)
                self.log_data(output, **kwargs)

    def get_staff_list(self):
        self.log('Fetching a staff list from\n  {}'.format(self.base_url))
        soup = get_html_parser(self.base_url)
        staff_members = parse_staff_links(soup, Parser.staff_div_id)
        self.log('Fetched a staff list containing {} entries'.format(len(staff_members)))

        return staff_members

    def get_personal_page(self, personal_page_suffix, index):
        url = self.personal_page_prefix + personal_page_suffix
        self.log('Fetching the staff member #{} from\n  {}' \
            .format(index+1, url))
        soup = get_html_parser(url)
        full_name, img, degree_string = parse_personal_page(soup, self.person_div_id)
        result = transform_full_name(full_name)
        if img:
            personal_image = self.personal_page_prefix + img
        else:
            personal_image = self.default_image
        degree = transform_degree(degree_string)
        result.update({
            'img': personal_image,
            'degree': degree,
        })
        self.log('Fetched a staff member: {}' \
            .format(result['last_name']), result)
        return result

    def get_personal_data(self, staff_links):
        for link in staff_links:
            personal_page = self.get_personal_page(link, staff_links.index(link))
            yield personal_page

    def write(self, filepath, results=None):
        if not results:
            results = self.results

        def write_result(filename, result):
            with open(filename, 'w', encoding='utf8') as file:
                json.dump(result, file,
                    indent=2 if self.options['pretty_output'] else None,
                    ensure_ascii=False)
            self.log('Written {}'.format(filename))

        write_result(filepath, results)

    def run(self):
        self.log('Fetching staff list from\n  {}'.format(self.base_url))
        staff_links = self.get_staff_list()
        self.log()
        self.log('{} staff members are found. Starting accumulating data...'
                .format(len(staff_links)))

        results = []
        parser = self.get_personal_data(staff_links)
        for result in parser:
            results.append(result)
        if self.options['file_path']:
            self.write(self.options['file_path'], results)
        self.results = results


if __name__ == '__main__':
    main()
