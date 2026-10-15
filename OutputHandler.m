/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "OutputHandler.h"

@implementation OutputHandler

- (id)initWithTarget:(NSString *)target {
    self = [super init];

    if (self) {
        buffer = [[NSMutableString alloc] init];

        if (!target) {
            outputTarget = @"stdout";
        } else if ([target isEqualToString:@"stdout"] ||
                   [target isEqualToString:@"stderr"] ||
                   [target isEqualToString:@"buffer"]) {
            outputTarget = target;
        } else if ([target isEqualToString:@"clipboard"]) {
            outputTarget = target;
            NSPasteboard *pasteboard = [NSPasteboard generalPasteboard];
            [pasteboard declareTypes:[NSArray arrayWithObject:NSStringPboardType] owner:nil];
            [pasteboard setString:@""
                          forType:NSStringPboardType];
        } else {
            NSFileManager *fm = [NSFileManager defaultManager];
            if ([fm fileExistsAtPath:target]) {
                if (![fm isWritableFileAtPath:target]) {
                    [NSException raise:@"InvalidDestinationException"
                                format:@"Cannot write to the file “%@” specified as output destination.", target];
                }
            } else {
                if (![fm createFileAtPath:target contents:nil attributes:nil]) {
                    [NSException raise:@"InvalidDestinationException"
                                format:@"Cannot create file “%@” specified as output destination.", target];
                }
            }
            outputTarget = target;
        }
    }
    return self;
}

- (void)dealloc {
    [buffer release];
    [super dealloc];
}

- (NSString *)buffer {
    return buffer;
}

- (void)write:(NSString *)message {
    if ([outputTarget isEqualToString:@"buffer"]) {
        if ([buffer length] > 0) {
            [buffer appendString:@"\n"];
        }
        [buffer appendString:message];
        return;
    }

    if ([outputTarget isEqualToString:@"stdout"]) {
        printf("%s\n", [message UTF8String]);
        return;
    }

    if ([outputTarget isEqualToString:@"stderr"]) {
        fprintf(stderr, "%s\n", [message UTF8String]);
        return;
    }

    if ([outputTarget isEqualToString:@"clipboard"]) {
        NSPasteboard *pasteboard = [NSPasteboard generalPasteboard];
        [pasteboard setString:[NSString stringWithFormat:@"%@%@\n", [pasteboard stringForType:NSStringPboardType], message]
                      forType:NSStringPboardType];
        return;
    }

    // Still here? must be file target
    NSFileHandle *fileHandle = [NSFileHandle fileHandleForWritingAtPath:outputTarget];
    [fileHandle seekToEndOfFile];
    [fileHandle writeData:[[message stringByAppendingString:@"\n"] dataUsingEncoding:NSUTF8StringEncoding]];
    [fileHandle closeFile];
}

@end
