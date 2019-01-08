import os
import stat
import glob
import shutil
from conans import ConanFile, AutoToolsBuildEnvironment, tools

_openSSL = "OpenSSL"

# based on https://github.com/conan-community/conan-ncurses/blob/stable/6.1/conanfile.py
class PjsipConan(ConanFile):
    name = "pjsip"
    version = "2.8"
    license = "GPL2"
    homepage = "https://github.com/totemic/pjproject"
    description = "PJSIP is a free and open source multimedia communication library written in C language implementing standard based protocols such as SIP, SDP, RTP, STUN, TURN, and ICE."
    url = "https://github.com/jens-totemic/conan-pjsip"    
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False],
               "SSL": [True, False],
               "fPIC": [True, False]}
    # if no OpenSSL is found, pjsip might try to use GnuTLS
    default_options = {"shared": False, "SSL": True, "fPIC": True}   
    generators = "cmake"
    exports = "LICENSE"
    _autotools = None
    _source_subfolder = "source_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
            del self.options.shared

    def source(self):
        tools.get("%s/archive/%s.zip" % (self.homepage, self.version))
        os.rename("pjproject-%s" % self.version, self._source_subfolder)
        if not tools.os_info.is_windows:
            configure_file = os.path.join(self._source_subfolder, "configure")
            stc = os.stat(configure_file)
            os.chmod(configure_file, stc.st_mode | stat.S_IEXEC)        
            aconfigure_file = os.path.join(self._source_subfolder, "aconfigure")
            stac = os.stat(aconfigure_file)
            os.chmod(aconfigure_file, stac.st_mode | stat.S_IEXEC)

    def requirements(self):
        if self.options.SSL:
            self.requires(_openSSL+"/1.0.2@conan/stable")

    def _configure_autotools(self):
        if not self._autotools:
            # Getting build errors when cross-compiling webrtc on ARM
            # since we don't use it, just disable it for now
            args = ["--disable-libwebrtc"]
            if self.options.shared: 
                args.append("--enable-shared")
            if self.options.SSL:
                openSSLroot = self.output.info(self.deps_cpp_info[_openSSL].rootpath)
                args.append("--with-ssl=" + str(openSSLroot))
            self._autotools = AutoToolsBuildEnvironment(self)
            self.output.info("Variables")
            #self.output.info(self.deps_cpp_info.lib_paths)
            self.output.info(self._autotools.library_paths)
            #self.output.info(self.deps_env_info.lib_paths)
            #vars = self._autotools.vars
            #vars["DYLD_LIBRARY_PATH"] = self._autotools.library_paths
            self.output.info(self._autotools.vars)
            
            #with tools.environment_append({"DYLD_LIBRARY_PATH": self._autotools.library_paths}):
            #    self.run("DYLD_LIBRARY_PATH=%s ./configure --enable-shared" % os.environ['DYLD_LIBRARY_PATH'])  
            #with tools.environment_append(self._autotools.vars):
            #    self.run("./configure --enable-shared")
            #    self.run("./configure '--enable-shared' '--prefix=/Users/jens/Develop/totemic/conan-pjsip/tmp/source/package' '--bindir=${prefix}/bin' '--sbindir=${prefix}/bin' '--libexecdir=${prefix}/bin' '--libdir=${prefix}/lib' '--includedir=${prefix}/include' '--oldincludedir=${prefix}/include' '--datarootdir=${prefix}/share' --build=x86_64-apple-darwin --host=x86_64-apple-darwin")

            copied_files = []
            # HACK: on OSX, if we compile using shared ssl libraries, a test program 
            # compiled by autoconfig does not find the dlyb files in its path, even if
            # we set the DYLD_LIBRARY_PATH correctly, propbably because sub process don't
            # inherit it. To fix it, we simply copy the shared libraries into the build
            # directory and delete them afterwards
            # see also https://stackoverflow.com/questions/33991581/install-name-tool-to-update-a-executable-to-search-for-dylib-in-mac-os-x/33992190#33992190
            for path in self._autotools.library_paths:
                for file in glob.glob(path+"/*.dylib"):
                    filename = file[len(path) + 1:]
                    print(filename)
                    copied_files.append(filename)
                    shutil.copy(file, ".")
            
            self._autotools.configure(args=args) #, vars=vars
            
            for copied_file in copied_files:
                os.remove(copied_file)
        return self._autotools
        
    def build(self):
        with tools.chdir(self._source_subfolder):
            autotools = self._configure_autotools()
            env_build_vars = autotools.vars
            # The include paths for dependencies are added to the CPPFLAGS
            # which are not used by pjsip's makefiles. Instead, add them to CFLAGS
            cflags = env_build_vars['CFLAGS'] + " " + env_build_vars['CPPFLAGS']
            env_build_vars['CFLAGS'] = cflags
            self.output.info(env_build_vars)
            # only build the lib target, we don't want to build the sample apps
            autotools.make(target="lib", vars=env_build_vars)

    def package(self):
#        self.copy("*.h", dst="include", src="hello")
#        self.copy("*hello.lib", dst="lib", keep_path=False)
#        self.copy("*.dll", dst="bin", keep_path=False)
#        self.copy("*.so", dst="lib", keep_path=False)
#        self.copy("*.dylib", dst="lib", keep_path=False)
#        self.copy("*.a", dst="lib", keep_path=False)

        self.copy("COPYING", dst="licenses", src=self._source_subfolder)
        with tools.chdir(self._source_subfolder):
            autotools = self._configure_autotools()
            autotools.install()

    def copy_cleaned(self, source, prefix, dest, excludes):
        for e in source:
            entry = e[len(prefix):] if e.startswith(prefix) else e
            if len(entry) > 0 and not entry in dest and not entry in excludes:
                dest.append(entry)

    def copy_prefix_merged(self, source, prefix, dest):
        cur_prefix = ""
        for e in source:
            if e == prefix:
                cur_prefix = prefix + " "
            else:                
                entry = cur_prefix + e
                if len(entry) > 0 and not entry in dest:
                    dest.append(entry)
                cur_prefix = ""

    def package_info(self):
        self.output.info("package_info")
        pkgconfigpath = os.path.join(self.package_folder, "lib/pkgconfig")
        self.output.info(pkgconfigpath)
        with tools.environment_append({'PKG_CONFIG_PATH': pkgconfigpath}):
            pkg_config = tools.PkgConfig("libpjproject")
            self.output.info(pkg_config.libs)
            self.output.info(pkg_config.libs_only_L)
            self.output.info(pkg_config.libs_only_l)
            self.output.info(pkg_config.libs_only_other)
            self.output.info(pkg_config.cflags)
            self.output.info(pkg_config.cflags_only_I)
            self.output.info(pkg_config.variables)
        self.copy_cleaned(pkg_config.libs_only_L, "-L", self.cpp_info.lib_paths, [])
        self.output.info(self.cpp_info.lib_paths)
        
        # exclude all libraries from dependencies here, they are separately included
        self.copy_cleaned(pkg_config.libs_only_l, "-l", self.cpp_info.libs, ["ssl", "crypto", "z"])
        self.output.info(self.cpp_info.libs)        
        
        self.copy_prefix_merged(pkg_config.libs_only_other, "-framework", self.cpp_info.exelinkflags)
        self.output.info(self.cpp_info.exelinkflags)
        self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags
        
#         self.cpp_info.libs = tools.collect_libs(self)
#         if self.settings.os == 'Macos':
#             for framework in ['CoreAudio',
#                               'CoreServices',
#                               'AudioUnit',
#                               'AudioToolbox',
#                               'Foundation',
#                               'AppKit',
#                               'AVFoundation',
#                               'CoreGraphics',
#                               'QuartzCore',
#                               'CoreVideo',
#                               'CoreMedia',
#                               'VideoToolbox']:
#                 self.cpp_info.exelinkflags.append('-framework %s' % framework)
#             self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags
