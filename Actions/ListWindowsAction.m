/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "ListWindowsAction.h"
#import <CoreGraphics/CoreGraphics.h>

@implementation ListWindowsAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"lw";
}

+ (NSString *)commandDescription {
    return @"  lw      Will print JSON listing all on-screen application windows with PID, title, and bounds.";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:@"List on-screen windows"];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    CFArrayRef windowList = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID);
    if (!windowList) {
        [options.commandOutputHandler write:@"[]\n"];
        return;
    }

    NSArray *windows = (__bridge NSArray *)windowList;
    NSMutableArray *result = [NSMutableArray array];

    for (NSDictionary *info in windows) {
        NSNumber *layer = [info objectForKey:(id)kCGWindowLayer];
        if ([layer intValue] != 0) continue;

        NSString *owner = [info objectForKey:(id)kCGWindowOwnerName];
        NSString *name = [info objectForKey:(id)kCGWindowName];
        NSNumber *pid = [info objectForKey:(id)kCGWindowOwnerPID];
        NSNumber *winId = [info objectForKey:(id)kCGWindowNumber];
        NSDictionary *bounds = [info objectForKey:(id)kCGWindowBounds];

        if (!owner && !name) continue;

        int w = [[bounds objectForKey:@"Width"] intValue];
        int h = [[bounds objectForKey:@"Height"] intValue];
        if (w < 10 || h < 10) continue;

        NSDictionary *winDict = [NSDictionary dictionaryWithObjectsAndKeys:
                                 owner ? owner : @"", @"application",
                                 name ? name : @"", @"title",
                                 pid ? pid : @0, @"pid",
                                 winId ? winId : @0, @"id",
                                 bounds ? bounds : @{}, @"bounds",
                                 nil];
        [result addObject:winDict];
    }

    CFRelease(windowList);

    NSData *jsonData = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    NSString *jsonString = [[[NSString alloc] initWithData:jsonData encoding:NSUTF8StringEncoding] autorelease];

    [options.commandOutputHandler write:jsonString];
    [options.commandOutputHandler write:@"\n"];
}

@end
