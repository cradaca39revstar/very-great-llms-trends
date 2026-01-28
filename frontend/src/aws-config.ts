/**
 * AWS Amplify configuration for Cognito (existing User Pool and App Client).
 * API contract: same User Pool / Client as backend; values from VITE_* env (Terraform outputs).
 */
import { Amplify } from 'aws-amplify';

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string | undefined;
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined;
const region = (import.meta.env.VITE_AWS_REGION as string | undefined) ?? 'us-east-1';

if (userPoolId && userPoolClientId) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: {
          email: true,
          password: true,
        },
      },
    },
  });
} else {
  console.warn(
    'AWS config missing: set VITE_COGNITO_USER_POOL_ID and VITE_COGNITO_CLIENT_ID (e.g. from terraform output -raw cognito_user_pool_id / cognito_client_id).'
  );
}

export { userPoolId, userPoolClientId, region };
