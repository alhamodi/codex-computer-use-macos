/**
 * Copyright (c) 2007-2021, Carsten Blüm <carsten@bluem.net>
 * All rights reserved.
 *
 * Upgraded for Computer Use.
 */

#import <Foundation/Foundation.h>

@interface OutputHandler : NSObject {
    NSString *outputTarget;
    NSMutableString *buffer;
}

- (id)initWithTarget:(NSString *)target;

- (void)write:(NSString *)message;

- (NSString *)buffer;

@end
