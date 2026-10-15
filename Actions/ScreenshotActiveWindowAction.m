/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "ScreenshotActiveWindowAction.h"
#import <ImageIO/ImageIO.h>
#import <ApplicationServices/ApplicationServices.h>

@implementation ScreenshotActiveWindowAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"scw";
}

+ (NSString *)commandDescription {
    return @"  scw:[path] Will capture a SCREENSHOT of only the focused frontmost window.\n"
    "          Example: “scw:/tmp/active.png”\n"
    "          Example: “scw” or “scw:-” (outputs base64 PNG string)";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    BOOL outputBase64 = [data isEqualToString:@""] || [data isEqualToString:@"-"];
    NSString *targetPath = outputBase64 ? nil : [data stringByStandardizingPath];

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:@"Capture screenshot of active window"];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    CGImageRef fullImage = CGDisplayCreateImage(CGMainDisplayID());
    if (NULL == fullImage) {
        [NSException raise:@"ScreenshotException" format:@"Failed to capture display image"];
    }

    NSScreen *mainScreen = [NSScreen mainScreen];
    CGFloat scale = [mainScreen backingScaleFactor];

    NSRunningApplication *app = [[NSWorkspace sharedWorkspace] frontmostApplication];
    pid_t pid = [app processIdentifier];
    CGRect cropRect = CGRectZero;
    BOOL gotBounds = NO;

    AXUIElementRef appRef = AXUIElementCreateApplication(pid);
    if (appRef) {
        AXUIElementRef windowRef = NULL;
        AXError err = AXUIElementCopyAttributeValue(appRef, kAXFocusedWindowAttribute, (CFTypeRef *)&windowRef);
        if (err == kAXErrorSuccess && windowRef) {
            CGPoint pos = CGPointZero;
            CGSize size = CGSizeZero;
            AXValueRef posVal = NULL;
            AXValueRef sizeVal = NULL;
            AXUIElementCopyAttributeValue(windowRef, kAXPositionAttribute, (CFTypeRef *)&posVal);
            AXUIElementCopyAttributeValue(windowRef, kAXSizeAttribute, (CFTypeRef *)&sizeVal);
            if (posVal) AXValueGetValue(posVal, kAXValueTypeCGPoint, &pos);
            if (sizeVal) AXValueGetValue(sizeVal, kAXValueTypeCGSize, &size);
            if (posVal) CFRelease(posVal);
            if (sizeVal) CFRelease(sizeVal);
            CFRelease(windowRef);

            if (size.width > 10 && size.height > 10) {
                cropRect = CGRectMake(pos.x * scale, pos.y * scale, size.width * scale, size.height * scale);
                gotBounds = YES;
            }
        }
        CFRelease(appRef);
    }

    CGImageRef finalImage = NULL;
    if (gotBounds) {
        finalImage = CGImageCreateWithImageInRect(fullImage, cropRect);
    }
    if (!finalImage) {
        finalImage = fullImage; // Fallback to full screen if window bounds unavailable
    } else {
        CGImageRelease(fullImage);
    }

    CFStringRef pngType = (CFStringRef)@"public.png";

    if (outputBase64) {
        NSMutableData *pngData = [NSMutableData data];
        CGImageDestinationRef dest = CGImageDestinationCreateWithData((CFMutableDataRef)pngData, pngType, 1, NULL);
        if (dest) {
            CGImageDestinationAddImage(dest, finalImage, NULL);
            CGImageDestinationFinalize(dest);
            CFRelease(dest);
            CGImageRelease(finalImage);

            NSString *base64String = [pngData base64EncodedStringWithOptions:0];
            [options.commandOutputHandler write:base64String];
            [options.commandOutputHandler write:@"\n"];
        } else {
            CGImageRelease(finalImage);
            [NSException raise:@"ScreenshotException" format:@"Failed to create image destination"];
        }
    } else {
        NSURL *fileURL = [NSURL fileURLWithPath:targetPath];
        CGImageDestinationRef dest = CGImageDestinationCreateWithURL((CFURLRef)fileURL, pngType, 1, NULL);
        if (dest) {
            CGImageDestinationAddImage(dest, finalImage, NULL);
            BOOL success = CGImageDestinationFinalize(dest);
            CFRelease(dest);
            CGImageRelease(finalImage);
            if (!success) {
                [NSException raise:@"ScreenshotException" format:@"Failed to write PNG file: %@", targetPath];
            }
        } else {
            CGImageRelease(finalImage);
            [NSException raise:@"ScreenshotException" format:@"Failed to open destination file: %@", targetPath];
        }
    }
}

@end
