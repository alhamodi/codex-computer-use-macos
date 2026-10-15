/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "ScreenshotAction.h"
#import <ImageIO/ImageIO.h>

@implementation ScreenshotAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"sc";
}

+ (NSString *)commandDescription {
    return @"  sc:[path] Will capture a SCREENSHOT of the display.\n"
    "          If a path is provided, saves the screenshot as a PNG file.\n"
    "          If no path or “-” is given, outputs base64-encoded PNG string.\n"
    "          Example: “sc:/tmp/screen.png”\n"
    "          Example: “sc” or “sc:-”";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    BOOL outputBase64 = [data isEqualToString:@""] || [data isEqualToString:@"-"];
    NSString *targetPath = outputBase64 ? nil : [data stringByStandardizingPath];

    if (MODE_REGULAR != options.mode) {
        if (outputBase64) {
            [options.verbosityOutputHandler write:@"Capture screenshot to stdout as base64 PNG"];
        } else {
            [options.verbosityOutputHandler write:[NSString stringWithFormat:@"Capture screenshot to %@", targetPath]];
        }
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    CGImageRef screenImage = CGDisplayCreateImage(CGMainDisplayID());
    if (NULL == screenImage) {
        [NSException raise:@"ScreenshotException"
                    format:@"Failed to capture screen image via CGDisplayCreateImage"];
    }

    CFStringRef pngType = (CFStringRef)@"public.png";

    if (outputBase64) {
        NSMutableData *pngData = [NSMutableData data];
        CGImageDestinationRef dest = CGImageDestinationCreateWithData((CFMutableDataRef)pngData, pngType, 1, NULL);
        if (NULL == dest) {
            CGImageRelease(screenImage);
            [NSException raise:@"ScreenshotException" format:@"Failed to create image destination"];
        }
        CGImageDestinationAddImage(dest, screenImage, NULL);
        CGImageDestinationFinalize(dest);
        CFRelease(dest);
        CGImageRelease(screenImage);

        NSString *base64String = [pngData base64EncodedStringWithOptions:0];
        [options.commandOutputHandler write:base64String];
        [options.commandOutputHandler write:@"\n"];
    } else {
        NSURL *fileURL = [NSURL fileURLWithPath:targetPath];
        CGImageDestinationRef dest = CGImageDestinationCreateWithURL((CFURLRef)fileURL, pngType, 1, NULL);
        if (NULL == dest) {
            CGImageRelease(screenImage);
            [NSException raise:@"ScreenshotException"
                        format:@"Failed to open destination file for writing: %@", targetPath];
        }
        CGImageDestinationAddImage(dest, screenImage, NULL);
        BOOL success = CGImageDestinationFinalize(dest);
        CFRelease(dest);
        CGImageRelease(screenImage);

        if (!success) {
            [NSException raise:@"ScreenshotException"
                        format:@"Failed to write screenshot PNG to file: %@", targetPath];
        }
    }
}

@end
