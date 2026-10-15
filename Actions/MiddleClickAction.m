/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "MiddleClickAction.h"
#include <unistd.h>

@implementation MiddleClickAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"mc";
}

+ (NSString *)commandDescription {
    return @"  mc:x,y  Will MIDDLE-CLICK at the point with the given coordinates.\n"
    "          Example: “mc:12,34” will middle-click at the point with x coordinate\n"
    "          12 and y coordinate 34. Instead of x and y values, you may\n"
    "          also use “.”, which means: the current position. Using “.” is\n"
    "          equivalent to using relative zero values “mc:+0,+0”.";
}

#pragma mark - MouseBaseAction

- (NSString *)actionDescriptionString:(NSString *)locationDescription {
    return [NSString stringWithFormat:@"Middle-click at %@", locationDescription];
}

- (void)performActionAtPoint:(CGPoint)p {
    CGEventRef centerDown = CGEventCreateMouseEvent(NULL, kCGEventOtherMouseDown, p, kCGMouseButtonCenter);
    CGEventSetIntegerValueField(centerDown, kCGMouseEventButtonNumber, 2);
    CGEventPost(kCGHIDEventTap, centerDown);
    CFRelease(centerDown);

    usleep(15000);

    CGEventRef centerUp = CGEventCreateMouseEvent(NULL, kCGEventOtherMouseUp, p, kCGMouseButtonCenter);
    CGEventSetIntegerValueField(centerUp, kCGMouseEventButtonNumber, 2);
    CGEventPost(kCGHIDEventTap, centerUp);
    CFRelease(centerUp);
}

@end
