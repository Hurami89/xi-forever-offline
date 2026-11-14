#!/usr/bin/env python3
"""Runs test_harvest.lua against the server's LuaJIT, the same interpreter the map server uses."""
import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = r"C:\ffxi-local\server"
DLL = os.path.join(SERVER, "libluajit_64.dll")

lib = ctypes.CDLL(DLL)
lib.luaL_newstate.restype = ctypes.c_void_p
lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
lib.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.luaL_loadfile.restype = ctypes.c_int
lib.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
lib.lua_pcall.restype = ctypes.c_int
lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
lib.lua_tolstring.restype = ctypes.c_char_p

def message(L):
    size = ctypes.c_size_t()
    text = lib.lua_tolstring(L, -1, ctypes.byref(size))
    return text.decode("utf-8", "replace") if text else "(no message)"

L = lib.luaL_newstate()
lib.luaL_openlibs(L)
script = os.path.join(HERE, "test_harvest.lua")
if lib.luaL_loadfile(L, script.encode()) != 0:
    print("LOAD ERROR:", message(L))
    sys.exit(2)
if lib.lua_pcall(L, 0, 0, 0) != 0:
    print("RUN ERROR:", message(L))
    sys.exit(1)
