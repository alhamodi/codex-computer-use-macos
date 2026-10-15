/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "ScreenInfoAction.h"

@implementation ScreenInfoAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"si";
}

+ (NSString *)commandDescription {
    return @"  si      Will print JSON with screen resolution and display information:\n"
    "          width, height, scale factor, and pixel dimensions for all displays.";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:@"Query screen and display information"];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    NSArray *screens = [NSScreen screens];
    NSMutableArray *screenList = [NSMutableArray arrayWithCapacity:[screens count]];

    for (NSUInteger i = 0; i < [screens count]; i++) {
        NSScreen *screen = [screens objectAtIndex:i];
        NSRect frame = [screen frame];
        CGFloat scale = [screen backingScaleFactor];
        NSRect visibleFrame = [screen visibleFrame];

        NSDictionary *screenDict = [NSDictionary dictionaryWithObjectsAndKeys:
                                    [NSNumber numberWithUnsignedInteger:i], @"index",
                                    [NSNumber numberWithBool:(screen == [NSScreen mainScreen])], @"is_main",
                                    [NSNumber numberWithDouble:frame.size.width], @"width",
                                    [NSNumber numberWithDouble:frame.size.height], @"height",
                                    [NSNumber numberWithDouble:scale], @"scale",
                                    [NSNumber numberWithInt:(int)round(frame.size.width * scale)], @"pixel_width",
                                    [NSNumber numberWithInt:(int)round(frame.size.height * scale)], @"pixel_height",
                                    [NSDictionary dictionaryWithObjectsAndKeys:
                                     [NSNumber numberWithDouble:visibleFrame.origin.x], @"x",
                                     [NSNumber numberWithDouble:visibleFrame.origin.y], @"y",
                                     [NSNumber numberWithDouble:visibleFrame.size.width], @"width",
                                     [NSNumber numberWithDouble:visibleFrame.size.height], @"height",
                                     nil], @"visible_frame",
                                    nil];
        [screenList addObject:screenDict];
    }

    NSDictionary *result = [NSDictionary dictionaryWithObject:screenList forKey:@"screens"];
    NSData *jsonData = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    NSString *jsonString = [[[NSString alloc] initWithData:jsonData encoding:NSUTF8StringEncoding] autorelease];

    [options.commandOutputHandler write:jsonString];
    [options.commandOutputHandler write:@"\n"];
}

@end
