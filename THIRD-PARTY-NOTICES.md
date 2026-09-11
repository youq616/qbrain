# Third-party notices

Qbrain retains the upstream MIT license in `LICENSE`. Original Qbrain baseline: `Lordakee/qbrain@2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`. The optimization nodes use independent C++ implementations inspired by gbrain and OpenViking, not their vendored source.

## JSON for Modern C++ 3.11.3 (nlohmann/json)

Copyright (c) 2013-2023 Niels Lohmann

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Source: bundled `third_party/nlohmann/json.hpp`; https://github.com/nlohmann/json/tree/v3.11.3

## SQLite 3.46.1

SQLite is in the public domain. The bundled amalgamation includes FTS5. Source:
`third_party/sqlite/sqlite-amalgamation-3460100`, https://sqlite.org/copyright.html

## Optional PostgreSQL client

The native build may support a separately installed libpq through a delay-loaded import. This package does not bundle PostgreSQL server, libpq or its external dependencies. Those components have their own licenses. The new automatic-memory/context modules use SQLite only.

## Operating-system components

Windows libraries are linked using the Windows SDK. This ZIP does not bundle a model, model weights, fonts or third-party Agent clients.
