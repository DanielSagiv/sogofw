SHELL = /bin/sh
INCLUDE = \
    -I../usr/include/sys \
    -I../Headers

CC    = gcc -I/lib/ -w  -fmessage-length=0 -lstdc++
#CC    = gcc -I/lib/ -w  -fmessage-length=0 -fPIC -lstdc++
CCDEPMODE =
#CFLAGS =  -g -O2 -std=gnu99
CFLAGS =  -g -O2 -Wl,--stack,33554432 -std=gnu99
CPP =
CPPFLAGS =

CXX = g++  -I/lib/ -w -c -fmessage-length=0 -fPIC -lstdc++
CXXCPP =
CXXDEPMODE = depmode=gcc3
CXXFLAGS =  -g -O2

FLAGS        = -std=gnu99 -Iinclude
DEBUGFLAGS   = -O0 -D _DEBUG
RELEASEFLAGS = -O2 -D NDEBUle:29: *** missing sepG -combine -fwhole-program

#LDFLAGS =  -L$(SDKCOMP)/x86_64 -ldl -lpthread  -lstdc++ -lIDTechSDK -rdynamic -lcrypto -Wl,-rpath,.
#LDFLAGS =  -L$(SDKCOMP)/x86_64 -ldl -lpthread  -lstdc++ -lIDTechSDK -rdynamic -Wl,-rpath,.
LDFLAGS =  -ldl -lpthread  -lstdc++ -Wl,-rpath,.

LIBOBJS =
LIBS =
LIBTOOL =

TARGET  = test_demo
SOURCES = $(shell echo ../*.c)
HEADERS = $(shell echo ../*.h)

CSRCS = $(wildcard ../*.c)
CPPSRCS = $(wildcard ../*.cpp)
COBJS := $(CSRCS:.c=.o)
CPPOBJS := $(CPPSRCS:.cpp=.o)

PREFIX = $(DESTDIR)/usr/local
BINDIR = $(PREFIX)/bin

all: $(TARGET)
clean:
	rm -f $(COBJS) $(CPPOBJS) $(TARGET)
$(TARGET) : $(COBJS) $(CPPOBJS)
	$(CC) -o $(TARGET) $(COBJS) $(CPPOBJS) $(LIBS) -o $@ $(LDFLAGS)

	rm -f *.o
	rm -f ../*.o

$(OTHERDEMOS):
	$(MAKE) -C $@ clean && $(MAKE) -C $@

.PHONY: all $(OTHERDEMOS)
