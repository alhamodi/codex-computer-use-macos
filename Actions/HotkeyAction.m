/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "HotkeyAction.h"
#import "KeyPressAction.h"
#import "KeycodeInformer.h"
#include <unistd.h>

@implementation HotkeyAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"hk";
}

+ (NSString *)commandDescription {
    return @"  hk:keys Will trigger a HOTKEY (key combination), pressing modifier keys,\n"
    "          hitting the target key, and releasing the modifier keys.\n"
    "          Keys can be separated by comma or plus (+).\n"
    "          Modifiers: cmd, shift, alt/opt, ctrl, fn\n"
    "          Target key: any character or named key (return, space, tab, esc, etc.)\n"
    "          Example: “hk:cmd,c” (copy)\n"
    "          Example: “hk:cmd+shift+p”\n"
    "          Example: “hk:cmd,space” (Spotlight search)";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    NSString *shortcut = [[self class] commandShortcut];

    if ([data isEqualToString:@""]) {
        [NSException raise:@"InvalidCommandException"
                    format:@"Missing argument to command “%@”. Example: “%@:cmd,c”", shortcut, shortcut];
    }

    BOOL endsWithPlus = NO;
    NSString *dataToParse = data;
    if ([dataToParse hasSuffix:@"++"] || [dataToParse hasSuffix:@",+"]) {
        endsWithPlus = YES;
        dataToParse = [dataToParse substringToIndex:[dataToParse length] - 1];
        if ([dataToParse hasSuffix:@"+"] || [dataToParse hasSuffix:@","]) {
            dataToParse = [dataToParse substringToIndex:[dataToParse length] - 1];
        }
    }

    NSString *normalizedData = [dataToParse stringByReplacingOccurrencesOfString:@"+" withString:@","];
    NSArray *rawTokens = [normalizedData componentsSeparatedByString:@","];
    NSMutableArray *tokens = [NSMutableArray arrayWithCapacity:[rawTokens count] + 1];

    for (NSString *token in rawTokens) {
        NSString *trimmed = [token stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([trimmed length] > 0) {
            [tokens addObject:[trimmed lowercaseString]];
        }
    }

    if (endsWithPlus) {
        [tokens addObject:@"+"];
    }

    if ([tokens count] < 2) {
        [NSException raise:@"InvalidCommandException"
                    format:@"Hotkey requires at least one modifier and one key. Given: “%@”", data];
    }

    NSDictionary *modifierMap = [NSDictionary dictionaryWithObjectsAndKeys:
                                 @55, @"cmd",
                                 @55, @"command",
                                 @56, @"shift",
                                 @58, @"alt",
                                 @58, @"opt",
                                 @58, @"option",
                                 @59, @"ctrl",
                                 @59, @"control",
                                 @63, @"fn",
                                 nil];

    NSMutableArray *modifierCodes = [NSMutableArray array];
    NSMutableArray *modifierNames = [NSMutableArray array];
    NSString *targetKey = nil;

    for (NSUInteger i = 0; i < [tokens count]; i++) {
        NSString *token = [tokens objectAtIndex:i];
        NSNumber *modCode = [modifierMap objectForKey:token];
        if (modCode != nil && i < [tokens count] - 1) {
            [modifierCodes addObject:modCode];
            [modifierNames addObject:token];
        } else {
            // Target key
            targetKey = token;
        }
    }

    if (targetKey == nil) {
        [NSException raise:@"InvalidCommandException"
                    format:@"No target key specified in hotkey “%@”", data];
    }

    CGKeyCode targetKeyCode = 0;
    BOOL foundKey = NO;

    NSDictionary *specialKeys = [KeyPressAction getSupportedKeycodes];
    NSString *codeStr = [specialKeys objectForKey:targetKey];
    if (codeStr != nil) {
        targetKeyCode = (CGKeyCode)[codeStr intValue];
        foundKey = YES;
    } else {
        // ANSI keycode table for standard Latin characters and symbols
        // guarantees shortcuts work regardless of current active keyboard layout (e.g. Arabic)
        static NSDictionary *ansiKeys = nil;
        if (!ansiKeys) {
            ansiKeys = [[NSDictionary alloc] initWithObjectsAndKeys:
                        @0, @"a", @1, @"s", @2, @"d", @3, @"f", @4, @"h", @5, @"g", @6, @"z", @7, @"x",
                        @8, @"c", @9, @"v", @11, @"b", @12, @"q", @13, @"w", @14, @"e", @15, @"r", @16, @"y",
                        @17, @"t", @18, @"1", @19, @"2", @20, @"3", @21, @"4", @22, @"6", @23, @"5",
                        @24, @"=", @24, @"+", @24, @"plus", @25, @"9", @26, @"7", @27, @"-", @27, @"minus",
                        @28, @"8", @29, @"0", @30, @"]", @31, @"o", @32, @"u", @33, @"[", @34, @"i", @35, @"p",
                        @37, @"l", @38, @"j", @39, @"'", @39, @"quote", @40, @"k", @41, @";", @42, @"\\",
                        @43, @",", @43, @"comma", @44, @"/", @44, @"slash", @45, @"n", @46, @"m", @47, @".",
                        @47, @"period", @50, @"`", nil];
        }

        NSNumber *ansiNum = [ansiKeys objectForKey:targetKey];
        if (ansiNum != nil) {
            targetKeyCode = (CGKeyCode)[ansiNum intValue];
            foundKey = YES;
        } else {
            NSArray *codes = [[KeycodeInformer sharedInstance] keyCodesForString:targetKey];
            if ([codes count] > 0) {
                NSArray *firstInfo = [codes objectAtIndex:0];
                targetKeyCode = (CGKeyCode)[[firstInfo objectAtIndex:0] intValue];
                foundKey = YES;
            }
        }
    }

    if (!foundKey) {
        [NSException raise:@"InvalidCommandException"
                    format:@"Unrecognized target key “%@” in hotkey “%@”", targetKey, data];
    }

    NSString *desc = [NSString stringWithFormat:@"Hotkey: %@ + %@",
                      [modifierNames componentsJoinedByString:@"+"], targetKey];

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:desc];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    // Step 1: Press modifier keys down
    for (NSNumber *modCode in modifierCodes) {
        CGEventRef ev = CGEventCreateKeyboardEvent(NULL, (CGKeyCode)[modCode intValue], true);
        CGEventPost(kCGSessionEventTap, ev);
        CFRelease(ev);
        usleep(10000);
    }

    // Step 2: Press target key down and up
    CGEventRef keyDown = CGEventCreateKeyboardEvent(NULL, targetKeyCode, true);
    CGEventPost(kCGSessionEventTap, keyDown);
    CFRelease(keyDown);

    usleep(20000);

    CGEventRef keyUp = CGEventCreateKeyboardEvent(NULL, targetKeyCode, false);
    CGEventPost(kCGSessionEventTap, keyUp);
    CFRelease(keyUp);

    usleep(10000);

    // Step 3: Release modifier keys in reverse order
    for (NSInteger i = (NSInteger)[modifierCodes count] - 1; i >= 0; i--) {
        NSNumber *modCode = [modifierCodes objectAtIndex:(NSUInteger)i];
        CGEventRef ev = CGEventCreateKeyboardEvent(NULL, (CGKeyCode)[modCode intValue], false);
        CGEventPost(kCGSessionEventTap, ev);
        CFRelease(ev);
        usleep(10000);
    }
}

@end
