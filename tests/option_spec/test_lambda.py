# coding: spec

from aws_syncr.option_spec.lambdas import (
      Lambdas, Lambda, lambdas_spec, __register__
    , divisible_by_spec, function_handler_spec, function_code_spec, only_one_spec
    , S3Code, InlineCode, DirectoryCode
    )

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.errors import BadSpecValue
from input_algorithms.meta import Meta
from option_merge import MergedOptions
from contextlib import contextmanager
from tests.helpers import TestCase
from textwrap import dedent
import zipfile
import shutil
import uuid
import mock
import os

describe TestCase, "only_one_spec":
    before_each:
        self.meta = Meta({}, [])

    it "allows through if the normalised val is not a list":
        val = mock.Mock(name="val")
        res = mock.Mock(name="res")
        spec = mock.Mock(name="spec")
        spec.normalise.return_value = res
        self.assertIs(only_one_spec(spec).normalise(self.meta, val), res)
        spec.normalise.assert_called_once_with(self.meta, val)

    it "complains if the normalised value is a list with zero items":
        val = mock.Mock(name="val")
        res = []
        spec = mock.Mock(name="spec")
        spec.normalise.return_value = res
        with self.fuzzyAssertRaisesError(BadSpecValue, "Please only specify one value"):
            self.assertIs(only_one_spec(spec).normalise(self.meta, val), res)
        spec.normalise.assert_called_once_with(self.meta, val)

    it "complains if the normalised value is a list with more than one items":
        v1 = mock.Mock(name='v1')
        v2 = mock.Mock(name='v2')
        val = mock.Mock(name="val")
        res = [v1, v2]
        spec = mock.Mock(name="spec")
        spec.normalise.return_value = res
        with self.fuzzyAssertRaisesError(BadSpecValue, "Please only specify one value"):
            self.assertIs(only_one_spec(spec).normalise(self.meta, val), res)
        spec.normalise.assert_called_once_with(self.meta, val)

describe TestCase, "divisible_by_spec":
    before_each:
        self.meta = Meta({}, [])

    it "complains if the value is not an integer":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Expected an integer"):
            divisible_by_spec(2).normalise(self.meta, "adsf")

    it "complains if the value is not divisible":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Value should be divisible by 2"):
            divisible_by_spec(2).normalise(self.meta, 25)

    it "allows numbers that are divisble":
        self.assertEqual(divisible_by_spec(2).normalise(self.meta, 16), 16)

describe TestCase, "function_handler_spec":
    before_each:
        self.meta = Meta({}, [])

    it "returns as is if value is specified":
        val = str(uuid.uuid1())
        self.assertEqual(function_handler_spec().normalise(self.meta, val), val)

    it "formats val if specified":
        val = "{hi}"
        ident = str(uuid.uuid1())
        self.meta.everything = MergedOptions.using({"hi": ident})
        self.assertEqual(function_handler_spec().normalise(self.meta, val), ident)

    describe "NotSpecified":
        it "complains if runtime is java":
            self.meta.everything = MergedOptions.using({"lambda": {"function": {"runtime": "java8"}}})
            meta = self.meta.at("lambda").at("function").at("handler")
            with self.fuzzyAssertRaisesError(BadSpecValue, "No default function handler for java", meta=meta):
                function_handler_spec().normalise(meta, NotSpecified)

        it "returns index.handler for runtime of nodejs":
            self.meta.everything = MergedOptions.using({"lambda": {"function": {"runtime": "nodejs"}}})
            meta = self.meta.at("lambda").at("function").at("handler")
            self.assertEqual(function_handler_spec().normalise(meta, NotSpecified), "index.handler")

        it "returns lambda_function.lambda_handler for runtime of python2.7":
            self.meta.everything = MergedOptions.using({"lambda": {"function": {"runtime": "python2.7"}}})
            meta = self.meta.at("lambda").at("function").at("handler")
            self.assertEqual(function_handler_spec().normalise(meta, NotSpecified), "lambda_function.lambda_handler")

        it "complains about other runtimes":
            self.meta.everything = MergedOptions.using({"lambda": {"function": {"runtime": "asdf"}}})
            meta = self.meta.at("lambda").at("function").at("handler")
            with self.fuzzyAssertRaisesError(BadSpecValue, "No default function handler for asdf", meta=meta):
                function_handler_spec().normalise(meta, NotSpecified)

describe TestCase, "function_code_spec":
    before_each:
        self.meta = Meta({}, [])

    it "complains if there are keys other than s3, inline or directory":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Expected one of the available choices", available=["s3", "inline", "directory"], got="other"):
            try:
                function_code_spec().normalise(self.meta, {"other": 2})
            except BadSpecValue as error:
                self.assertEqual(len(error.errors), 1)
                raise error.errors[0]

    it "commplains if you specify more than one of s3, inline or directory":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Please only specify one of s3, inline or directory for your code", meta=self.meta):
            function_code_spec().normalise(self.meta, {"s3": 2, "directory": ""})

    it "returns S3Code object if you specify s3":
        ret = function_code_spec().normalise(self.meta, {"s3": {"key": "somewhere", "bucket": "another"}})
        self.assertEqual(ret.s3_address, "s3://another/somewhere")

    it "returns InlineCode object if you specify inline":
        ident = str(uuid.uuid1())
        ident2 = str(uuid.uuid1())
        self.meta.everything = MergedOptions.using({"lambda": {"function": {"runtime": ident}}})
        meta = self.meta.at("lambda").at("function").at("handler")
        ret = function_code_spec().normalise(meta, {"inline": ident2})
        self.assertEqual(ret.code, ident2)
        self.assertEqual(ret.runtime, ident)
        self.assertEqual(ret.s3_address, None)

    it "returns DirectoryCode object if you specify directory":
        with self.a_directory() as directory:
            ret = function_code_spec().normalise(self.meta, {"directory": directory})
        self.assertEqual(ret.directory, directory)
        self.assertEqual(ret.s3_address, None)

    it "returns DirectoryCode with exclude if you specify directory as dictionary":
        exclude = str(uuid.uuid1())
        with self.a_directory() as directory:
            ret = function_code_spec().normalise(self.meta, {"directory": {"directory": directory, "exclude": [exclude]}})
        self.assertEqual(ret.directory, directory)
        self.assertEqual(ret.s3_address, None)
        self.assertEqual(ret.exclude, [exclude])

    it "complains if DirectoryCode is given a directory that doesn't exist":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Got something that didn't exist"):
            with self.a_directory() as directory:
                shutil.rmtree(directory)
                try:
                    ret = function_code_spec().normalise(self.meta, {"directory": directory})
                except BadSpecValue as error:
                    self.assertEqual(len(error.errors), 1)
                    raise error.errors[0]

describe TestCase, "lambdas_spec":
    it "overrides the function name with the key of the specification":
        spec = MergedOptions.using({"name": "overridden", "location": "ap-southeast-2", "code": {"inline": "blah"}, "role": "arn", "runtime": "python2.7"})
        everything = MergedOptions.using({"lambda": {"function": spec}})
        result = lambdas_spec().normalise(Meta(everything, [('lambda', ""), ('function', "")]), spec)
        self.assertEqual(result.name, "function")

    it "merges with a template":
        spec = MergedOptions.using({"use": "blah", "code": {"inline": "codez"}, "timeout": 30, "runtime": "python2.7"})
        everything = MergedOptions.using({"lambda": {"function": spec}, "templates": {"blah": {"location": "ap-southeast-2", "role": "arn"}}})
        result = lambdas_spec().normalise(Meta(everything, []).at("lambda").at("function"), spec)
        self.assertEqual(result
            , Lambda(
                  name="function", location="ap-southeast-2", code={"code":"codez", "runtime":"python2.7"}, runtime="python2.7"
                , handler="lambda_function.lambda_handler", memory_size=128, timeout=30, sample_event=""
                , description = '', role="arn"
                )
            )

    it "must ensure memory_size is divisble by 64":
        spec = MergedOptions.using({"name": "overridden", "location": "ap-southeast-2", "code": {"inline": "blah"}, "role": "arn", "runtime": "python2.7"})
        spec["memory_size"] = 63
        everything = MergedOptions.using({"lambda": {"function": spec}})
        with self.fuzzyAssertRaisesError(BadSpecValue, "Value should be divisible by 64"):
            try:
                lambdas_spec().normalise(Meta(everything, [('lambda', ""), ('function', "")]), spec)
            except BadSpecValue as error:
                self.assertEqual(len(error.errors), 1)
                raise error.errors[0]

describe TestCase, "Lambdas":
    describe "Syncing a function":
        before_each:
            self.name = mock.Mock(name="name")
            self.role = mock.Mock(name="role")
            self.code = mock.Mock(name="code")
            self.timeout = mock.Mock(name="timeout")
            self.runtime = mock.Mock(name="runtime")
            self.location = mock.Mock(name="location")
            self.description = mock.Mock(name="description")
            self.sample_event = mock.Mock(name="sample_event")
            self.memory_size = mock.Mock(name="memory_size")
            self.handler = mock.Mock(name="handler")

            self.function = Lambda(
                  name=self.name, role=self.role, code=self.code, timeout=self.timeout
                , runtime=self.runtime, location=self.location, description=self.description
                , sample_event=self.sample_event, memory_size=self.memory_size, handler=self.handler
                )
            self.lambdas = Lambdas(items={self.name: self.function})

            self.amazon = mock.Mock(name="amazon")
            self.aws_syncr = mock.Mock(name="aws_syncr")

        it "can create a bucket that doesn't exist":
            lambdas = self.amazon.lambdas = mock.Mock(name="lambdas")
            lambdas.function_info.return_value = {}
            self.lambdas.sync_one(self.aws_syncr, self.amazon, self.function)
            lambdas.function_info.assert_called_once_with(self.name, self.location)
            lambdas.create_function.assert_called_once_with(self.name, self.description, self.location, self.runtime, self.role, self.handler, self.timeout, self.memory_size, self.code)

        it "can modify a function that does exist":
            lambdas = self.amazon.lambdas = mock.Mock(name="lambdas")
            function_info = mock.Mock(name="function_info")
            lambdas.function_info.return_value = function_info
            self.lambdas.sync_one(self.aws_syncr, self.amazon, self.function)
            lambdas.function_info.assert_called_once_with(self.name, self.location)
            lambdas.modify_function.assert_called_once_with(function_info, self.name, self.description, self.location, self.runtime, self.role, self.handler, self.timeout, self.memory_size, self.code)

describe TestCase, "S3Code":
    it "can get an s3 address":
        sc = S3Code(key="a/path/to/something", bucket="a_bucket", version=1)
        self.assertEqual(sc.s3_address, "s3://a_bucket/a/path/to/something")

describe TestCase, "InlineCode":
    it "has an s3 address of None":
        ic = InlineCode("codez", "python2.7")
        self.assertIs(ic.s3_address, None)

    describe "arcname":
        it "gives lambda_function.py if runtime is python2.7":
            self.assertEqual(InlineCode("", "python2.7").arcname, "./lambda_function.py")

        it "gives main.java if runtime is java8":
            self.assertEqual(InlineCode("", "java8").arcname, "./main.java")

        it "gives index.js if runtime is nodejs":
            self.assertEqual(InlineCode("", "nodejs").arcname, "./index.js")

    describe "code_in_file":
        it "yields a filename containing the codez":
            code = """
                def hello_world(self):
                    print("hello_world")
            """

            with InlineCode(code, "python2.7").code_in_file() as filename:
                self.assertIs(os.path.isfile(filename), True)
                with open(filename) as fle:
                    self.assertEqual(fle.read(), dedent(code))

    describe "zipfile":
        it "yields a zipfile with the code at arcname":
            an = str(uuid.uuid1())
            code = "./{0}".format(str(uuid.uuid1()))
            class sub(InlineCode):
                arcname = an

            ic = sub(code, "python2.7")
            with ic.zipfile() as zf:
                with self.a_directory() as directory:
                    zipfile.ZipFile(zf).extractall(directory)
                    self.assertEqual(os.listdir(directory), [an])
                    with open(os.path.join(directory, an)) as fle:
                        self.assertEqual(fle.read(), code)

describe TestCase, "DirectoryCode":
    before_each:
        self.p1, self.c1 = str(uuid.uuid1()), str(uuid.uuid1())
        self.p2, self.c2 = str(uuid.uuid1()), str(uuid.uuid1())

        self.subdir = str(uuid.uuid1())
        self.p3 = os.path.join(self.subdir, str(uuid.uuid1()))
        self.c3 = str(uuid.uuid1())

        self.p4 = os.path.join(self.subdir, str(uuid.uuid1()))
        self.c4 = str(uuid.uuid1())

        self.granddir = str(uuid.uuid1())
        self.p5 = os.path.join(self.subdir, self.granddir, str(uuid.uuid1()))
        self.c5 = str(uuid.uuid1())

        self.paths = {
              self.p1: self.c1
            , self.p2: self.c2
            , self.p3: self.c3
            , self.p4: self.c4
            , self.p5: self.c5
            }

    @contextmanager
    def make_directory(self):
        with self.a_directory() as directory:
            for path, content in self.paths.items():
                location = os.path.join(directory, path)
                parent = os.path.dirname(location)
                if not os.path.exists(parent):
                    os.makedirs(parent)

                with open(location, "w") as fle:
                    fle.write(content)
            yield directory

    it "has an s3 address of None":
        dc = DirectoryCode("a_path", [])
        self.assertIs(dc.s3_address, None)

    describe "files":
        it "yields all the files":
            with self.make_directory() as directory:
                found = list(DirectoryCode(directory, []).files())
            self.assertEqual(sorted(found), sorted([
                  (os.path.join(directory, self.p1), self.p1)
                , (os.path.join(directory, self.p2), self.p2)
                , (os.path.join(directory, self.p3), self.p3)
                , (os.path.join(directory, self.p4), self.p4)
                , (os.path.join(directory, self.p5), self.p5)
                ]))

        it "excludes files with the exclude functionality":
            with self.make_directory() as directory:
                found = list(DirectoryCode(directory, ["{0}/*".format(self.subdir)]).files())
            self.assertEqual(sorted(found), sorted([
                  (os.path.join(directory, self.p1), self.p1)
                , (os.path.join(directory, self.p2), self.p2)
                ]))

    describe "zipfile":
        it "includes the files from the files method":
            with self.make_directory() as directory:
                files = [
                      (os.path.join(directory, self.p1), self.p1)
                    , (os.path.join(directory, self.p3), self.p3)
                    ]
                dc = DirectoryCode(directory, [])
                with mock.patch.object(dc, "files", lambda: files):
                    with self.a_directory() as dir2:
                        with dc.zipfile() as filename:
                            zipfile.ZipFile(filename).extractall(dir2)
                        self.assertEqual(sorted(os.listdir(dir2)), [self.p1, self.subdir])
                        self.assertEqual(os.listdir(os.path.join(dir2, self.subdir)), [os.path.basename(self.p3)])

                        with open(os.path.join(dir2, self.p1)) as fle:
                            self.assertEqual(fle.read(), self.c1)

                        with open(os.path.join(dir2, self.p3)) as fle:
                            self.assertEqual(fle.read(), self.c3)

describe TestCase, "__register__":
    before_each:
        self.function1 = {
              'role': "arn:etc:1", 'code': {"inline": "codez"}
            , 'timeout': 30, 'runtime': "python2.7"
            , 'location': "ap-southeast-2", 'description': "a function!"
            , 'sample_event': "sample", 'memory_size': 192
            }

        self.function2 = {
              'role': "arn:etc:2", 'code': {"inline": "memory_leak_factory()"}
            , 'timeout': 3, 'runtime': "nodejs"
            , 'location': "ap-southeast-2", 'description': "another function!"
            , 'sample_event': "sample2", 'memory_size': 256
            }

        self.everything = MergedOptions.using({"lambda": {"func1": self.function1, "func2": self.function2}})
        self.meta = Meta(self.everything, [])

    it "works":
        lambdas = __register__()[(22, 'lambda')].normalise(self.meta.at("lambda"), self.everything['lambda'].wrapped())
        self.assertEqual(lambdas, Lambdas({
              "func1": Lambda(
                  name="func1", role="arn:etc:1", code=InlineCode("codez", "python2.7"), timeout=30, runtime="python2.7"
                , location="ap-southeast-2", description="a function!", sample_event="sample", memory_size=192
                , handler="lambda_function.lambda_handler"
                )
            , "func2": Lambda(
                  name="func2", role="arn:etc:2", code=InlineCode("memory_leak_factory()", "nodejs"), timeout=3
                , runtime="nodejs", location="ap-southeast-2", description="another function!", sample_event="sample2"
                , memory_size=256, handler="index.handler"
                )
            })
        )

