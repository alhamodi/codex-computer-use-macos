/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "WindowInfoAction.h"
#import <ApplicationServices/ApplicationServices.h>

@implementation WindowInfoAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"wi";
}

+ (NSString *)commandDescription {
    return @"  wi      Will print JSON with frontmost application and active window information:\n"
    "          application name, bundle identifier, PID, window title, and bounds.";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:@"Query frontmost application and window information"];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    NSRunningApplication *app = [[NSWorkspace sharedWorkspace] frontmostApplication];

    NSMutableDictionary *windowDict = [NSMutableDictionary dictionary];
    NSString *appName = [app localizedName] ? [app localizedName] : @"";
    NSString *bundleId = [app bundleIdentifier] ? [app bundleIdentifier] : @"";
    pid_t pid = [app processIdentifier];

    [windowDict setObject:appName forKey:@"application"];
    [windowDict setObject:bundleId forKey:@"bundle_id"];
    [windowDict setObject:[NSNumber numberWithInt:pid] forKey:@"pid"];

    AXUIElementRef appRef = AXUIElementCreateApplication(pid);
    if (appRef) {
        AXUIElementRef windowRef = NULL;
        AXError err = AXUIElementCopyAttributeValue(appRef, kAXFocusedWindowAttribute, (CFTypeRef *)&windowRef);
        if (err == kAXErrorSuccess && windowRef) {
            CFTypeRef titleRef = NULL;
            AXUIElementCopyAttributeValue(windowRef, kAXTitleAttribute, &titleRef);
            if (titleRef) {
                [windowDict setObject:(__bridge NSString *)titleRef forKey:@"window_title"];
                CFRelease(titleRef);
            } else {
                [windowDict setObject:@"" forKey:@"window_title"];
            }

            CGPoint pos = CGPointZero;
            CGSize size = CGSizeZero;
            AXValueRef posVal = NULL;
            AXValueRef sizeVal = NULL;
            AXUIElementCopyAttributeValue(windowRef, kAXPositionAttribute, (CFTypeRef *)&posVal);
            AXUIElementCopyAttributeValue(windowRef, kAXSizeAttribute, (CFTypeRef *)&sizeVal);

            if (posVal) {
                AXValueGetValue(posVal, kAXValueTypeCGPoint, &pos);
                CFRelease(posVal);
            }
            if (sizeVal) {
                AXValueGetValue(sizeVal, kAXValueTypeCGSize, &size);
                CFRelease(sizeVal);
            }

            NSDictionary *boundsDict = [NSDictionary dictionaryWithObjectsAndKeys:
                                        [NSNumber numberWithDouble:pos.x], @"x",
                                        [NSNumber numberWithDouble:pos.y], @"y",
                                        [NSNumber numberWithDouble:size.width], @"width",
                                        [NSNumber numberWithDouble:size.height], @"height",
                                        nil];
            [windowDict setObject:boundsDict forKey:@"bounds"];
            CFRelease(windowRef);
        }
        CFRelease(appRef);
    }

    NSData *jsonData = [NSJSONSerialization dataWithJSONObject:windowDict options:NSJSONWritingPrettyPrinted error:nil];
    NSString *jsonString = [[[NSString alloc] initWithData:jsonData encoding:NSUTF8StringEncoding] autorelease];

    [options.commandOutputHandler write:jsonString];
    [options.commandOutputHandler write:@"\n"];
}

@end
