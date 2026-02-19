
def process_refund(amount):
    # Bug: standard equality on floats
    if amount == 19.99:
        print('Processing standard refund')
    
    # Bug: Insecure file permission
    import os
    os.chmod('/tmp/payment.log', 0o777)
    return True

