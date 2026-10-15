CC = cc 
CFLAGS = -include cliclick_Prefix.pch -I Actions -I . -mmacosx-version-min=14.0 -Wno-deprecated-declarations

all: macros cliclick

macros:
	./generate-action-classes-macro.sh

cliclick: Actions/ClickAction.o \
          Actions/ColorPickerAction.o \
          Actions/DoubleclickAction.o \
          Actions/DragDownAction.o \
          Actions/DragUpAction.o \
          Actions/DragMoveAction.o \
          Actions/FocusAppAction.o \
          Actions/HotkeyAction.o \
          Actions/KeyBaseAction.o \
          Actions/KeyDownAction.o \
          Actions/KeyDownUpBaseAction.o \
          Actions/KeyPressAction.o \
          Actions/KeyUpAction.o \
          Actions/ListWindowsAction.o \
          Actions/MiddleClickAction.o \
          Actions/MouseBaseAction.o \
          Actions/MoveAction.o \
          Actions/PrintAction.o \
          Actions/RightClickAction.o \
          Actions/ScreenInfoAction.o \
          Actions/ScreenshotAction.o \
          Actions/ScreenshotActiveWindowAction.o \
          Actions/ScrollAction.o \
          Actions/TripleclickAction.o \
          Actions/TypeAction.o \
          Actions/VisionOcrAction.o \
          Actions/WaitAction.o \
          Actions/WindowInfoAction.o \
          ActionExecutor.o \
          KeycodeInformer.o \
          OutputHandler.o \
          cliclick.o
	$(CC) -o cliclick $^ -framework Cocoa -framework Carbon -framework ApplicationServices -framework ImageIO -framework Vision

ActionExecutor.o: ActionClassesMacro.h ActionExecutor.m
	$(CC) $(CFLAGS) -c -o $@ ActionExecutor.m

install: macros cliclick
	cp cliclick /usr/local/bin/

clean:
	$(RM) -v ActionClassesMacro.h
	$(RM) -v *.o Actions/*.o
	$(RM) -vr cliclick
