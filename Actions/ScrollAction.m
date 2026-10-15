/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "ScrollAction.h"
#import "MouseBaseAction.h"
#import "MoveAction.h"
#include <unistd.h>
#include <stdlib.h>

@implementation ScrollAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"s";
}

+ (NSString *)commandDescription {
    return @"  s:coords,dy[,dx] Will SCROLL vertically (and optionally horizontally).\n"
    "          Example: “s:500,300,-5” will scroll down 5 lines at position 500,300.\n"
    "          Example: “s:.,-10” will scroll down 10 lines at current mouse location.\n"
    "          Example: “s:-5” will scroll down 5 lines at current location.\n"
    "          (Positive dy scrolls up, negative dy scrolls down.)";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    NSString *shortcut = [[self class] commandShortcut];

    if ([data isEqualToString:@""]) {
        [NSException raise:@"InvalidCommandException"
                    format:@"Missing argument to command “%@”. Examples: “%@:500,300,-5” or “%@:.,-10” or “%@:-5”",
                           shortcut, shortcut, shortcut, shortcut];
    }

    NSArray *tokens = [data componentsSeparatedByString:@","];
    CGPoint targetPoint;
    int deltaY = 0;
    int deltaX = 0;
    BOOL moveMouse = NO;

    CGEventRef dummyEvent = CGEventCreate(NULL);
    CGPoint currentLoc = CGEventGetLocation(dummyEvent);
    CFRelease(dummyEvent);

    if ([tokens count] == 1) {
        // Just deltaY at current location
        deltaY = [[tokens objectAtIndex:0] intValue];
        targetPoint = currentLoc;
    } else if ([tokens count] == 2 && [[tokens objectAtIndex:0] isEqualToString:@"."]) {
        // Current location: .,deltaY
        deltaY = [[tokens objectAtIndex:1] intValue];
        targetPoint = currentLoc;
    } else if ([tokens count] == 3 && [[tokens objectAtIndex:0] isEqualToString:@"."]) {
        // Current location: .,deltaY,deltaX
        deltaY = [[tokens objectAtIndex:1] intValue];
        deltaX = [[tokens objectAtIndex:2] intValue];
        targetPoint = currentLoc;
    } else if ([tokens count] >= 3) {
        // Coordinates given: x,y,deltaY[,deltaX]
        targetPoint.x = [MouseBaseAction getCoordinate:[tokens objectAtIndex:0] forAxis:XAXIS];
        targetPoint.y = [MouseBaseAction getCoordinate:[tokens objectAtIndex:1] forAxis:YAXIS];
        deltaY = [[tokens objectAtIndex:2] intValue];
        if ([tokens count] >= 4) {
            deltaX = [[tokens objectAtIndex:3] intValue];
        }
        moveMouse = YES;
    } else {
        [NSException raise:@"InvalidCommandException"
                    format:@"Invalid arguments “%@” to command “%@”. Examples: “%@:500,300,-5” or “%@:.,-10” or “%@:-5”",
                           data, shortcut, shortcut, shortcut, shortcut];
    }

    if (MODE_REGULAR != options.mode) {
        NSString *desc = [NSString stringWithFormat:@"Scroll at %d,%d (deltaY: %d, deltaX: %d)",
                          (int)targetPoint.x, (int)targetPoint.y, deltaY, deltaX];
        [options.verbosityOutputHandler write:desc];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    if (moveMouse) {
        MoveAction *mover = [[MoveAction alloc] init];
        NSString *posStr = [NSString stringWithFormat:@"=%d,=%d", (int)targetPoint.x, (int)targetPoint.y];
        [mover performActionWithData:posStr withOptions:options];
        [mover release];
    }

    CGEventRef scrollEvent = CGEventCreateScrollWheelEvent2(NULL,
                                                            kCGScrollEventUnitLine,
                                                            2,
                                                            (int32_t)deltaY,
                                                            (int32_t)deltaX,
                                                            0);
    if (scrollEvent) {
        CGEventSetLocation(scrollEvent, targetPoint);
        CGEventPost(kCGHIDEventTap, scrollEvent);
        CFRelease(scrollEvent);
    }
}

@end
