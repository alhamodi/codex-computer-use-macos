/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "FocusAppAction.h"

@implementation FocusAppAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"fa";
}

+ (NSString *)commandDescription {
    return @"  fa:app_or_pid Will FOCUS/ACTIVATE an application by name or process ID.\n"
    "          Example: “fa:Safari”\n"
    "          Example: “fa:1234”";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    if ([data isEqualToString:@""]) {
        [NSException raise:@"InvalidCommandException"
                    format:@"Missing argument to command “%@”. Example: “%@:Safari”",
                           [[self class] commandShortcut], [[self class] commandShortcut]];
    }

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:[NSString stringWithFormat:@"Activate application: %@", data]];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    // Check if data is purely a numeric PID
    NSScanner *scanner = [NSScanner scannerWithString:data];
    int pid = 0;
    BOOL isPurePid = [scanner scanInt:&pid] && [scanner isAtEnd] && pid > 0;
    BOOL activated = NO;

    if (isPurePid) {
        NSRunningApplication *app = [NSRunningApplication runningApplicationWithProcessIdentifier:pid];
        if (app) {
            activated = [app activateWithOptions:(NSApplicationActivateIgnoringOtherApps | NSApplicationActivateAllWindows)];
        }
    }

    if (!activated) {
        for (NSRunningApplication *app in [[NSWorkspace sharedWorkspace] runningApplications]) {
            if ([[app localizedName] caseInsensitiveCompare:data] == NSOrderedSame) {
                activated = [app activateWithOptions:(NSApplicationActivateIgnoringOtherApps | NSApplicationActivateAllWindows)];
                break;
            }
        }
    }

    if (MODE_VERBOSE == options.mode) {
        [options.verbosityOutputHandler write:[NSString stringWithFormat:@"Activate %@: %@", data, activated ? @"YES" : @"NO"]];
    }
}

@end
