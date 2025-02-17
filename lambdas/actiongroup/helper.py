import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('steakhouse_bookings')


def get_named_parameter(event, name):
    """
    Get a parameter from the lambda event
    """
    return next((item['value'] for item in event.get('parameters', []) if item['name'] == name), None)

def get_booking_details(booking_id):
    """
    Retrieve details of a steakhouse booking

    Args:
        booking_id (string): The ID of the booking to retrieve
    """
    try:
        response = table.get_item(Key={'booking_id': booking_id})
        if 'Item' in response:
            return response['Item']
        else:
            return {'message': f'No booking found with ID {booking_id}'}
    except Exception as e:
        return {'error': str(e)}
