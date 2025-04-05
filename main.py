from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from google.cloud import bigquery_data_exchange_v1beta1 
from google.api_core import exceptions
from google.iam.v1 import policy_pb2

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for flash messages

# Initialize the Analytics Hub client
analytics_hub_client = bigquery_data_exchange_v1beta1.AnalyticsHubServiceClient() 

def get_data_exchanges(project_id, location="us"):
    """Get all data exchanges in the project."""
    parent = f"projects/{project_id}/locations/{location}"
    try:
        exchanges = analytics_hub_client.list_data_exchanges(request={"parent": parent})
        return [(exchange.name.split('/')[-1], exchange.display_name) for exchange in exchanges]
    except Exception as e:
        print(f"Error fetching data exchanges: {e}")
        return []

def get_listings(project_id, exchange_id, location="us"):
    """Get all listings in a data exchange."""
    parent = f"projects/{project_id}/locations/{location}/dataExchanges/{exchange_id}"
    try:
        listings = analytics_hub_client.list_listings(request={"parent": parent})
        return [(listing.name.split('/')[-1], listing.display_name) for listing in listings]
    except Exception as e:
        print(f"Error fetching listings: {e}")
        return []

@app.route('/')
def index():
    enter project id = 'enter project id'
    if not enter project id:
        flash('No project ID found. Please make sure you are authenticated and have set the project ID.', 'error')
        return render_template('index.html', project_id=None, data_exchanges=[])
    data_exchanges = get_data_exchanges(project_id)
    return render_template('index.html', project_id=project_id, data_exchanges=data_exchanges)

@app.route('/get-listings/<exchange_id>')
def get_listings_route(exchange_id):
    project_id = 'enter project id'
    if not project_id:
        return jsonify({'error': 'No project ID found'}), 400
    listings = get_listings(project_id, exchange_id)
    return jsonify(listings)

@app.route('/manage-access', methods=['POST'])
def manage_access():
    try:
        action = request.form['action']
        project_id = request.form['project_id']
        exchange_id = request.form['exchange_id']
        listing_id = request.form['listing_id']
        email = request.form['email']
        location = "us"

        listing_path = f"projects/{project_id}/locations/{location}/dataExchanges/{exchange_id}/listings/{listing_id}"

        if action == 'grant':
            # Create policy using protocol buffer objects
            policy = policy_pb2.Policy()
            binding = policy_pb2.Binding()
            binding.role = 'roles/analyticshub.subscriber'
            binding.members.append(f'user:{email}')
            policy.bindings.append(binding)

            analytics_hub_client.set_iam_policy(
                request={
                    'resource': listing_path,
                    'policy': policy
                }
            )
            flash(f'Access granted to {email}', 'success')

        elif action == 'revoke':
            # Get current policy and remove user
            current_policy = analytics_hub_client.get_iam_policy(request={'resource': listing_path})
            new_policy = policy_pb2.Policy()
            
            for binding in current_policy.bindings:
                new_binding = policy_pb2.Binding()
                new_binding.role = binding.role
                
                if binding.role == 'roles/analyticshub.subscriber':
                    members = [m for m in binding.members if m != f'user:{email}']
                    if members:
                        new_binding.members.extend(members)
                        new_policy.bindings.append(new_binding)
                else:
                    new_binding.members.extend(binding.members)
                    new_policy.bindings.append(new_binding)

            analytics_hub_client.set_iam_policy(
                request={
                    'resource': listing_path,
                    'policy': new_policy
                }
            )
            flash(f'Access revoked for {email}', 'success')

    except exceptions.PermissionDenied:
        flash('Permission denied. Please check your credentials and permissions.', 'error')
    except exceptions.NotFound:
        flash('Resource not found. Please check your listing details.', 'error')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        print(f"Error details: {str(e)}")  # For debugging

    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
