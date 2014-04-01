import sys
import inspect
import traceback

from SimpleXMLRPCServer import SimpleXMLRPCServer
from argparse import ArgumentParser
from StringIO import StringIO

from robot.libraries.OperatingSystem import OperatingSystem


class RobotRemoteServer(SimpleXMLRPCServer):
    allow_reuse_address = True

    def __init__(self, port):
        self._port = int(port)
        self._shutdown = False
        self._registry = {}

        SimpleXMLRPCServer.__init__(self, ("", self._port), logRequests=False)

        self.register_function(self.get_keyword_names)
        self.register_function(self.get_keyword_arguments)
        self.register_function(self.get_keyword_documentation)
        self.register_function(self.run_keyword)
        self.register_function(self.stop_remote_server)

        self.startup()

    def startup(self):
        print 'Robot Framework remote server starting at port %s' % self._port

        self._shutdown = False

        while not self._shutdown:
            self.handle_request()

    def stop_remote_server(self):
        print 'Robot Framework remote server at %s stopping' % self._port

        self._shutdown = True

        return True

    def get_keyword_names(self):
        registry = self._registry

        registry['stop_remote_server'] = RobotRemoteServer
        registry.update({k: OperatingSystem for k in RobotRemoteServer._get_keyword_names(OperatingSystem)})

        return sorted(registry.keys())

    @staticmethod
    def _get_keyword_names(library):
        kw_names = getattr(library, 'get_keyword_names', None) or getattr(library, 'getKeywordNames', None)

        if inspect.isroutine(kw_names):
            names = kw_names()
        else:
            names = [name for name in dir(library) if name[0] != '_' and inspect.isroutine(getattr(library, name))]

        return names

    def get_keyword_arguments(self, name):
        kw = self._get_keyword(name)
        args = self._get_keyword_arguments(kw)
        return args

    @staticmethod
    def _get_keyword_arguments(kw):
        args, varargs, _, defaults = inspect.getargspec(kw)

        if inspect.ismethod(kw):
            args = args[1:]  # drop 'self'

        if defaults:
            args, names = args[:-len(defaults)], args[-len(defaults):]
            args += ['%s=%s' % (n, d) for n, d in zip(names, defaults)]

        if varargs:
            args.append('*%s' % varargs)

        return args

    def get_keyword_documentation(self, name):
        if name == '__intro__':
            return inspect.getdoc(RobotRemoteServer)

        if name == '__init__' and inspect.ismodule(RobotRemoteServer):
            return ''

        return inspect.getdoc(self._get_keyword(name)) or ''

    def _get_keyword(self, name, library=None):
        kw = getattr(library or self._registry[name], name, None)
        return kw if inspect.isroutine(kw) else None

    def run_keyword(self, name, args):
        result = {
            'status': 'PASS',
            'return': '',
            'output': '',
            'error': '',
            'traceback': ''
        }

        # Intercept stdout
        sys.stdout = StringIO()

        # noinspection PyBroadException
        try:
            return_value = self._get_keyword(name)(*args)
        except:
            result['status'] = 'FAIL'
            result['error'], result['traceback'] = self._get_error_details()
        else:
            result['return'] = self._handle_return_value(return_value)

        # Restore stdout
        output = sys.stdout.getvalue()
        sys.stdout.close()
        sys.stdout = sys.__stdout__

        result['output'] = output

        return result

    @staticmethod
    def _handle_return_value(ret):
        if isinstance(ret, (basestring, int, long, float)):
            return ret
        if isinstance(ret, (tuple, list)):
            return [RobotRemoteServer._handle_return_value(item) for item in ret]
        if isinstance(ret, dict):
            return dict([((str(key) if key else ''), RobotRemoteServer._handle_return_value(value))
                         for key, value in ret.items()])

        return str(ret) if ret else ''

    @staticmethod
    def _get_error_details():
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type in (SystemExit, KeyboardInterrupt):
            # Restore stdout
            sys.stdout.close()
            sys.stdout = sys.__stdout__

            raise

        return (RobotRemoteServer._get_error_message(exc_type, exc_value),
                RobotRemoteServer._get_error_traceback(exc_tb))

    @staticmethod
    def _get_error_message(exc_type, exc_value):
        name = exc_type.__name__
        message = str(exc_value)

        if not message:
            return name

        if name in ('AssertionError', 'RuntimeError', 'Exception'):
            return message

        return '%s: %s' % (name, message)

    @staticmethod
    def _get_error_traceback(exc_tb):
        # Latest entry originates from this class so it can be removed
        entries = traceback.extract_tb(exc_tb)[1:]
        trace = ''.join(traceback.format_list(entries))
        return 'Traceback (most recent call last):\n' + trace


def start(args):
    RobotRemoteServer(args.port)


def main():
    parser = ArgumentParser(add_help=False)
    parser.set_defaults(func=start)
    parser.add_argument('-p', action='store', dest='port', default=8270)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
