/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <time.h>
#import <Cocoa/Cocoa.h>
#import "ActionExecutor.h"
#import "MoveAction.h"
#import "OutputHandler.h"
#import "ExecutionOptions.h"

void error(void);
void help(void);

NSArray* parseCommandsFile(NSString *filepath);
NSArray* parseJsonToActions(id jsonObj, NSError **error);

int main (int argc, const char * argv[]) {

    NSAutoreleasePool * pool = [[NSAutoreleasePool alloc] init];

    struct ExecutionOptions executionOptions;
    executionOptions.easing = 0;
    executionOptions.waitTime = 0;
    executionOptions.mode = MODE_REGULAR;
    NSArray *modeOptionArg;
    NSString *verbosityOutputDestination = nil;
    NSString *filepath = nil;
    NSString *commandOutputDestination = nil;
    NSString *jsonInputString = nil;
    BOOL isJsonMode = NO;
    NSArray *actions = nil;
    CGPoint initialMousePosition;
    BOOL restoreOption = NO;
    int optchar;

    if (! AXIsProcessTrusted()) {
        fprintf(stderr, "WARNING: Accessibility privileges not enabled. Many actions may fail.\n");
        fprintf(stderr, "         Enable the checkbox for the containing app in:\n");
        fprintf(stderr, "         System Preferences → Security & Privacy → Accessibility\n");
    }

    while ((optchar = getopt(argc, (char * const *)argv, "horVne:f:d:m:w:j:")) != -1) {
        switch(optchar) {
            case 'h':
                help();
                [pool release];
                return EXIT_SUCCESS;
            case 'V':
                printf("%s\n", [[NSString stringWithFormat:@"cliclick %@ (Computer Use Edition), %@", VERSION, RELEASEDATE] UTF8String]);
                [pool release];
                return EXIT_SUCCESS;
            case 'n':
                [[NSWorkspace sharedWorkspace] openURL:[NSURL URLWithString:DONATIONS_URL]];
                [pool release];
                return EXIT_SUCCESS;
            case 'o':
                [[NSWorkspace sharedWorkspace] openURL:[NSURL URLWithString:HISTORY_URL]];
                [pool release];
                return EXIT_SUCCESS;
            case 'j':
                isJsonMode = YES;
                jsonInputString = [NSString stringWithCString:optarg encoding:NSUTF8StringEncoding];
                break;
            case 'm':
                modeOptionArg = [[NSString stringWithCString:optarg encoding:NSASCIIStringEncoding] componentsSeparatedByString:@":"];
                if ([[modeOptionArg objectAtIndex:0] isEqualToString:@"verbose"]) {
                    executionOptions.mode = MODE_VERBOSE;
                } else if ([[modeOptionArg objectAtIndex:0] isEqualToString:@"test"]) {
                    executionOptions.mode = MODE_TEST;
                } else {
                    fprintf(stderr, "Only “verbose” or “test” are valid values for the -m argument\n");
                    [pool release];
                    return EXIT_FAILURE;
                }
                if ([modeOptionArg count] > 1 && [modeOptionArg objectAtIndex:1]) {
                    verbosityOutputDestination = [modeOptionArg objectAtIndex:1];
                }
                break;
            case 'e':
                executionOptions.easing = atoi(optarg) > 0 ? atoi(optarg) : 0;
                break;
            case 'f':
                filepath = [NSString stringWithCString:optarg encoding:NSASCIIStringEncoding];
                break;
            case 'd':
                commandOutputDestination = [NSString stringWithCString:optarg encoding:NSASCIIStringEncoding];
                break;
            case 'r':
                restoreOption = YES;
                break;
            case 'w':
                executionOptions.waitTime = atoi(optarg) > 0 ? atoi(optarg) : 0;
                break;
            default:
                [pool release];
                return EXIT_FAILURE;
        }
    }

    if (isJsonMode && !commandOutputDestination) {
        commandOutputDestination = @"buffer";
    }

    @try {
        executionOptions.commandOutputHandler = [[OutputHandler alloc] initWithTarget:commandOutputDestination];
        executionOptions.verbosityOutputHandler = [[OutputHandler alloc] initWithTarget:verbosityOutputDestination];
    }
    @catch (NSException *e) {
        if (isJsonMode) {
            NSDictionary *errResp = [NSDictionary dictionaryWithObjectsAndKeys:
                                     @"error", @"status",
                                     [e reason], @"error", nil];
            NSData *d = [NSJSONSerialization dataWithJSONObject:errResp options:0 error:nil];
            printf("%s\n", [[[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding] autorelease].UTF8String);
        } else {
            fprintf(stderr, "%s\n", [[e reason] UTF8String]);
        }
        [pool release];
        return EXIT_FAILURE;
    }

    if (restoreOption) {
        CGEventRef ourEvent = CGEventCreate(NULL);
        initialMousePosition = CGEventGetLocation(ourEvent);
        CFRelease(ourEvent);
    }

    if (isJsonMode) {
        NSData *jsonData = nil;
        if ([jsonInputString isEqualToString:@"-"]) {
            jsonData = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
        } else {
            jsonData = [jsonInputString dataUsingEncoding:NSUTF8StringEncoding];
        }

        NSError *jsonErr = nil;
        id parsedObj = [NSJSONSerialization JSONObjectWithData:jsonData options:0 error:&jsonErr];
        if (jsonErr != nil || parsedObj == nil) {
            NSDictionary *errResp = [NSDictionary dictionaryWithObjectsAndKeys:
                                     @"error", @"status",
                                     [NSString stringWithFormat:@"Invalid JSON: %@", [jsonErr localizedDescription]], @"error", nil];
            NSData *d = [NSJSONSerialization dataWithJSONObject:errResp options:0 error:nil];
            printf("%s\n", [[[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding] autorelease].UTF8String);
            [pool release];
            return EXIT_FAILURE;
        }

        NSError *mappingErr = nil;
        actions = parseJsonToActions(parsedObj, &mappingErr);
        if (mappingErr != nil || actions == nil) {
            NSDictionary *errResp = [NSDictionary dictionaryWithObjectsAndKeys:
                                     @"error", @"status",
                                     [mappingErr localizedDescription], @"error", nil];
            NSData *d = [NSJSONSerialization dataWithJSONObject:errResp options:0 error:nil];
            printf("%s\n", [[[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding] autorelease].UTF8String);
            [pool release];
            return EXIT_FAILURE;
        }
    } else if (filepath) {
        NSFileManager *fm = [NSFileManager defaultManager];
        if ([filepath isEqualToString:@""]) {
            fprintf(stderr, "Option -f expects a path: -f /path/to/the/file\n");
            [pool release];
            return EXIT_FAILURE;
        }
        if (![filepath isEqualToString:@"-"] && ![fm fileExistsAtPath:filepath]) {
            fprintf(stderr, "There is no file at %s\n", [filepath UTF8String]);
            [pool release];
            return EXIT_FAILURE;
        }
        actions = parseCommandsFile(filepath);
    } else {
        if (optind == argc) {
            error();
            [pool release];
            return EXIT_FAILURE;
        }
        NSArray *arguments = [[NSProcessInfo processInfo] arguments];
        actions = [arguments subarrayWithRange:NSMakeRange(optind, argc - optind)];
    }

    if (executionOptions.mode == MODE_TEST) {
        [executionOptions.verbosityOutputHandler write:@"Running in test mode. These command(s) would be executed:"];
    }

    @try {
        [ActionExecutor executeActions:actions withOptions:executionOptions];
    }
    @catch (NSException *e) {
        if (isJsonMode) {
            NSDictionary *errResp = [NSDictionary dictionaryWithObjectsAndKeys:
                                     @"error", @"status",
                                     [e reason], @"error", nil];
            NSData *d = [NSJSONSerialization dataWithJSONObject:errResp options:0 error:nil];
            printf("%s\n", [[[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding] autorelease].UTF8String);
        } else {
            fprintf(stderr, "%s\n", [[e reason] UTF8String]);
        }
        [pool release];
        return EXIT_FAILURE;
    }

    if (restoreOption) {
        NSString *positionString = [NSString stringWithFormat:@"=%d,=%d", (int)initialMousePosition.x, (int)initialMousePosition.y];
        id moveAction = [[MoveAction alloc] init];
        [moveAction performActionWithData:positionString
                              withOptions:executionOptions];
        [moveAction release];
    }

    if (isJsonMode) {
        NSString *buf = [executionOptions.commandOutputHandler buffer];
        NSMutableDictionary *resp = [NSMutableDictionary dictionaryWithObjectsAndKeys:
                                     @"success", @"status", nil];
        if ([buf length] > 0) {
            // Check if buffer itself is JSON
            NSData *bufData = [buf dataUsingEncoding:NSUTF8StringEncoding];
            id parsedBuf = [NSJSONSerialization JSONObjectWithData:bufData options:0 error:nil];
            if (parsedBuf) {
                [resp setObject:parsedBuf forKey:@"data"];
            } else {
                [resp setObject:buf forKey:@"output"];
            }
        }
        NSData *d = [NSJSONSerialization dataWithJSONObject:resp options:NSJSONWritingPrettyPrinted error:nil];
        printf("%s\n", [[[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding] autorelease].UTF8String);
    }

    [pool release];
    return EXIT_SUCCESS;
}

NSArray* parseJsonToActions(id jsonObj, NSError **error) {
    NSArray *items = nil;
    if ([jsonObj isKindOfClass:[NSDictionary class]]) {
        items = [NSArray arrayWithObject:jsonObj];
    } else if ([jsonObj isKindOfClass:[NSArray class]]) {
        items = (NSArray *)jsonObj;
    } else {
        if (error) {
            *error = [NSError errorWithDomain:@"Cliclick" code:1
                                     userInfo:[NSDictionary dictionaryWithObject:@"Root JSON must be object or array" forKey:NSLocalizedDescriptionKey]];
        }
        return nil;
    }

    NSMutableArray *actions = [NSMutableArray array];

    for (id item in items) {
        if (![item isKindOfClass:[NSDictionary class]]) continue;
        NSDictionary *dict = (NSDictionary *)item;

        // Direct cliclick command string
        if ([dict objectForKey:@"command"]) {
            [actions addObject:[dict objectForKey:@"command"]];
            continue;
        }

        NSString *action = [[dict objectForKey:@"action"] lowercaseString];
        if (!action) continue;

        NSArray *coord = [dict objectForKey:@"coordinate"];

        if ([action isEqualToString:@"left_click"] || [action isEqualToString:@"click"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"c:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"c:."];
            }
        } else if ([action isEqualToString:@"right_click"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"rc:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"rc:."];
            }
        } else if ([action isEqualToString:@"middle_click"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"mc:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"mc:."];
            }
        } else if ([action isEqualToString:@"double_click"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"dc:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"dc:."];
            }
        } else if ([action isEqualToString:@"triple_click"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"tc:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"tc:."];
            }
        } else if ([action isEqualToString:@"mouse_move"] || [action isEqualToString:@"move"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"m:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            }
        } else if ([action isEqualToString:@"mouse_down"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"dd:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"dd:."];
            }
        } else if ([action isEqualToString:@"mouse_up"]) {
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"du:%@,%@", [coord objectAtIndex:0], [coord objectAtIndex:1]]];
            } else {
                [actions addObject:@"du:."];
            }
        } else if ([action isEqualToString:@"drag"] || [action isEqualToString:@"left_click_drag"]) {
            NSArray *from = [dict objectForKey:@"from"];
            NSArray *to = [dict objectForKey:@"to"] ? [dict objectForKey:@"to"] : coord;
            if (from && [from count] >= 2 && to && [to count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"dd:%@,%@", [from objectAtIndex:0], [from objectAtIndex:1]]];
                [actions addObject:[NSString stringWithFormat:@"dm:%@,%@", [to objectAtIndex:0], [to objectAtIndex:1]]];
                [actions addObject:[NSString stringWithFormat:@"du:%@,%@", [to objectAtIndex:0], [to objectAtIndex:1]]];
            } else if (to && [to count] >= 2) {
                [actions addObject:@"dd:."];
                [actions addObject:[NSString stringWithFormat:@"dm:%@,%@", [to objectAtIndex:0], [to objectAtIndex:1]]];
                [actions addObject:[NSString stringWithFormat:@"du:%@,%@", [to objectAtIndex:0], [to objectAtIndex:1]]];
            }
        } else if ([action isEqualToString:@"scroll"]) {
            int dy = [dict objectForKey:@"delta_y"] ? [[dict objectForKey:@"delta_y"] intValue] : 0;
            int dx = [dict objectForKey:@"delta_x"] ? [[dict objectForKey:@"delta_x"] intValue] : 0;
            if (coord && [coord count] >= 2) {
                [actions addObject:[NSString stringWithFormat:@"s:%@,%@,%d,%d", [coord objectAtIndex:0], [coord objectAtIndex:1], dy, dx]];
            } else {
                [actions addObject:[NSString stringWithFormat:@"s:.,%d,%d", dy, dx]];
            }
        } else if ([action isEqualToString:@"type"]) {
            NSString *text = [dict objectForKey:@"text"];
            if (text) {
                [actions addObject:[NSString stringWithFormat:@"t:%@", text]];
            }
        } else if ([action isEqualToString:@"key"] || [action isEqualToString:@"press_key"]) {
            NSString *k = [dict objectForKey:@"text"] ? [dict objectForKey:@"text"] : [dict objectForKey:@"key"];
            if (k) {
                [actions addObject:[NSString stringWithFormat:@"kp:%@", k]];
            }
        } else if ([action isEqualToString:@"hotkey"]) {
            id keys = [dict objectForKey:@"keys"];
            if ([keys isKindOfClass:[NSArray class]]) {
                [actions addObject:[NSString stringWithFormat:@"hk:%@", [keys componentsJoinedByString:@","]]];
            } else if ([keys isKindOfClass:[NSString class]]) {
                [actions addObject:[NSString stringWithFormat:@"hk:%@", keys]];
            }
        } else if ([action isEqualToString:@"wait"] || [action isEqualToString:@"sleep"]) {
            int ms = [dict objectForKey:@"ms"] ? [[dict objectForKey:@"ms"] intValue] : 100;
            [actions addObject:[NSString stringWithFormat:@"w:%d", ms]];
        } else if ([action isEqualToString:@"cursor_position"]) {
            [actions addObject:@"p:."];
        } else if ([action isEqualToString:@"screenshot"]) {
            NSString *p = [dict objectForKey:@"path"];
            if (p && [p length] > 0) {
                [actions addObject:[NSString stringWithFormat:@"sc:%@", p]];
            } else {
                [actions addObject:@"sc:-"];
            }
        } else if ([action isEqualToString:@"screen_info"]) {
            [actions addObject:@"si"];
        } else if ([action isEqualToString:@"window_info"]) {
            [actions addObject:@"wi"];
        } else if ([action isEqualToString:@"screenshot_active_window"]) {
            NSString *p = [dict objectForKey:@"path"];
            if (p && [p length] > 0) {
                [actions addObject:[NSString stringWithFormat:@"scw:%@", p]];
            } else {
                [actions addObject:@"scw:-"];
            }
        } else if ([action isEqualToString:@"extract_text"]) {
            [actions addObject:@"ocr"];
        } else if ([action isEqualToString:@"extract_text_active_window"]) {
            [actions addObject:@"ocr:active_window"];
        } else if ([action isEqualToString:@"list_windows"]) {
            [actions addObject:@"lw"];
        } else if ([action isEqualToString:@"focus_window"]) {
            NSString *app = [dict objectForKey:@"app_name"];
            NSNumber *pid = [dict objectForKey:@"pid"];
            if (pid && [pid intValue] > 0) {
                [actions addObject:[NSString stringWithFormat:@"fa:%d", [pid intValue]]];
            } else if (app && [app length] > 0) {
                [actions addObject:[NSString stringWithFormat:@"fa:%@", app]];
            }
        } else {
            if (error) {
                *error = [NSError errorWithDomain:@"Cliclick" code:2
                                         userInfo:[NSDictionary dictionaryWithObject:[NSString stringWithFormat:@"Unrecognized computer use action “%@”", action] forKey:NSLocalizedDescriptionKey]];
            }
            return nil;
        }
    }

    return actions;
}

NSArray* parseCommandsFile(NSString *filepath) {
    NSMutableArray *commands = [[NSMutableArray alloc] initWithCapacity:32];
    NSArray *lines;

    if ([filepath isEqualToString:@"-"]) {
        // stdin
        NSData *stdinData = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
        NSString *configString = [[NSString alloc] initWithData:stdinData encoding:NSUTF8StringEncoding];
        lines = [configString componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]];
        [configString release];
    } else {
        // File
        NSString *fileContents = [NSString stringWithContentsOfFile:filepath
                                                           encoding:NSUTF8StringEncoding
                                                              error:nil];
        lines = [fileContents componentsSeparatedByString:@"\n"];
    }

    NSUInteger i, count = [lines count];
    for (i = 0; i < count; i++) {
        NSString *command = [[lines objectAtIndex:i] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([command isEqualToString:@""]) {
            continue;
        }
        if ([[command substringToIndex:1] isEqualToString:@"#"]) {
            continue;
        }
        [commands addObject:command];
    }

    return [commands autorelease];
}

void error() {
    fprintf(stderr, "You did not pass any commands as argument to cliclick.\n");
    fprintf(stderr, "Call cliclick with option -h to see usage instructions.\n");
}

void help() {

    NSArray *actionClasses = [ActionExecutor actionClasses];
    NSUInteger i, count = [actionClasses count];

    NSString *help = @"\ncliclick (Computer Use Edition) is an advanced tool for executing mouse-,\n"
    "keyboard-, and display-related actions for desktop automation and AI agents.\n"
    "\n"
    "USAGE\n"
    "  cliclick [-r] [-m <mode>] [-d <target>] [-e <num>] [-f <file>] [-w <num>] [-j <json>] command1 [command2]\n"
    "\n"
    "OPTIONS\n"
    "  -j <json>   Execute actions passed as a JSON string or from stdin with “-j -”.\n"
    "              Compatible with Anthropic & Codex Computer Use action schemas.\n"
    "  -r          Restore initial mouse location when finished\n"
    "  -m <mode>   The mode can be either “verbose” or “test”\n"
    "  -d <target> Specify the target when using output commands (stdout, stderr, clipboard, buffer, or file path)\n"
    "  -e <easing> Set an easing factor for mouse movements\n"
    "  -f <file>   Read commands from file or stdin (“-f -”)\n"
    "  -w <num>    Wait the given number of milliseconds after each event\n"
    "  -V          Show cliclick version\n"
    "  -h          Show this help\n"
    "\n"
    "COMMANDS\n"
    "A command consists of an identifier, a colon, and arguments.\n\n"
    "LIST OF COMMANDS\n\n";

    printf("%s", [help UTF8String]);

    for (i = 0; i < count; i++) {
        NSString *className = [actionClasses objectAtIndex:i];
        printf("%s\n\n", [[NSClassFromString(className) commandDescription] UTF8String]);
    }
}
