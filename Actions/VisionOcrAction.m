/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import "VisionOcrAction.h"
#import <Vision/Vision.h>
#import <ApplicationServices/ApplicationServices.h>

@implementation VisionOcrAction

#pragma mark - ActionProtocol

+ (NSString *)commandShortcut {
    return @"ocr";
}

+ (NSString *)commandDescription {
    return @"  ocr:[active_window] Will extract on-screen TEXT and bounding boxes using Apple Vision OCR.\n"
    "          Example: “ocr” (extract text from entire screen)\n"
    "          Example: “ocr:active_window” (extract text from frontmost window)";
}

- (void)performActionWithData:(NSString *)data
                  withOptions:(struct ExecutionOptions)options {

    if (MODE_REGULAR != options.mode) {
        [options.verbosityOutputHandler write:@"Extract text from screen via Apple Vision OCR"];
    }

    if (MODE_TEST == options.mode) {
        return;
    }

    NSScreen *mainScreen = [NSScreen mainScreen];
    NSRect screenFrame = [mainScreen frame];
    CGFloat screenPtW = screenFrame.size.width;
    CGFloat screenPtH = screenFrame.size.height;

    CGImageRef image = CGDisplayCreateImage(CGMainDisplayID());
    if (!image) {
        [NSException raise:@"OCRException" format:@"Failed to capture screen for OCR"];
    }

    BOOL cropActiveWindow = [data isEqualToString:@"active_window"] || [data isEqualToString:@"window"];
    double offsetX = 0.0;
    double offsetY = 0.0;

    if (cropActiveWindow) {
        NSRunningApplication *app = [[NSWorkspace sharedWorkspace] frontmostApplication];
        pid_t pid = [app processIdentifier];
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

                CGFloat scale = [mainScreen backingScaleFactor];
                CGRect cropRect = CGRectMake(pos.x * scale, pos.y * scale, size.width * scale, size.height * scale);
                CGImageRef cropped = CGImageCreateWithImageInRect(image, cropRect);
                if (cropped) {
                    CGImageRelease(image);
                    image = cropped;
                    offsetX = pos.x;
                    offsetY = pos.y;
                    screenPtW = size.width;
                    screenPtH = size.height;
                }
            }
            CFRelease(appRef);
        }
    }

    NSMutableArray *lines = [NSMutableArray array];
    NSMutableString *fullText = [NSMutableString string];

    VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] initWithCompletionHandler:^(VNRequest *req, NSError *err) {
        if (err) return;
        NSArray *results = [req results];
        for (VNRecognizedTextObservation *obs in results) {
            VNRecognizedText *topText = [[obs topCandidates:1] firstObject];
            if (!topText) continue;

            NSString *str = [topText string];
            if ([fullText length] > 0) {
                [fullText appendString:@"\n"];
            }
            [fullText appendString:str];

            // Convert normalized bottom-left coords to top-left macOS point coordinates
            CGRect bbox = [obs boundingBox];
            double boxX = offsetX + (bbox.origin.x * screenPtW);
            double boxY = offsetY + ((1.0 - (bbox.origin.y + bbox.size.height)) * screenPtH);
            double boxW = bbox.size.width * screenPtW;
            double boxH = bbox.size.height * screenPtH;

            NSDictionary *lineDict = [NSDictionary dictionaryWithObjectsAndKeys:
                                      str, @"text",
                                      [NSNumber numberWithFloat:[topText confidence]], @"confidence",
                                      [NSDictionary dictionaryWithObjectsAndKeys:
                                       [NSNumber numberWithDouble:round(boxX)], @"x",
                                       [NSNumber numberWithDouble:round(boxY)], @"y",
                                       [NSNumber numberWithDouble:round(boxW)], @"width",
                                       [NSNumber numberWithDouble:round(boxH)], @"height",
                                       [NSNumber numberWithDouble:round(boxX + boxW / 2.0)], @"center_x",
                                       [NSNumber numberWithDouble:round(boxY + boxH / 2.0)], @"center_y",
                                       nil], @"box",
                                      nil];
            [lines addObject:lineDict];
        }
    }];
    [request setRecognitionLevel:VNRequestTextRecognitionLevelAccurate];

    VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithCGImage:image options:@{}];
    CGImageRelease(image);

    NSError *error = nil;
    [handler performRequests:@[request] error:&error];
    [request release];
    [handler release];

    NSDictionary *result = [NSDictionary dictionaryWithObjectsAndKeys:
                            fullText, @"text",
                            lines, @"lines",
                            [NSNumber numberWithUnsignedInteger:[lines count]], @"count",
                            nil];

    NSData *jsonData = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    NSString *jsonString = [[[NSString alloc] initWithData:jsonData encoding:NSUTF8StringEncoding] autorelease];

    [options.commandOutputHandler write:jsonString];
    [options.commandOutputHandler write:@"\n"];
}

@end
