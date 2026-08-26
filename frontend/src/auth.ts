import { SvelteKitAuth } from '@auth/sveltekit';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { PrismaClient } from '@prisma/client';
import Google from '@auth/core/providers/google';
import GitHub from '@auth/core/providers/github';
import Credentials from '@auth/core/providers/credentials';
import { env } from '$env/dynamic/private';
import { building } from '$app/environment';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

const prisma = new PrismaClient();

/** How long after account creation the session still advertises a new signup. */
const SIGNUP_FRESHNESS_MS = 60_000;

// Validate OAuth configuration (warn in development, throw in production for deployed apps)
function validateOAuthConfig() {
  const isProduction = env.NODE_ENV === 'production';
  const warnings: string[] = [];

  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET) {
    warnings.push('Google OAuth not configured (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)');
  }

  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) {
    warnings.push('GitHub OAuth not configured (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET)');
  }

  if (warnings.length > 0 && !building) {
    const message = warnings.join('; ');
    if (isProduction) {
      console.warn(`⚠️  OAuth Warning: ${message}. OAuth providers will be disabled.`);
    } else {
      console.warn(`⚠️  Development: ${message}. OAuth buttons may not work.`);
    }
  }
}

validateOAuthConfig();

// Build OAuth providers array - only include configured providers
function buildProviders() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const providers: any[] = [];

  // Credentials provider is always available
  providers.push(
    Credentials({
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });

          if (!res.ok) {
            return null;
          }

          const user = await res.json();
          return {
            id: user.id,
            email: user.email,
            name: user.name,
            image: user.image,
            role: user.role,
          };
        } catch (error) {
          console.error('Credentials auth error:', error);
          return null;
        }
      },
    })
  );

  // Only add Google if configured
  if (env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET) {
    providers.push(
      Google({
        clientId: env.GOOGLE_CLIENT_ID,
        clientSecret: env.GOOGLE_CLIENT_SECRET,
      })
    );
  }

  // Only add GitHub if configured
  if (env.GITHUB_CLIENT_ID && env.GITHUB_CLIENT_SECRET) {
    providers.push(
      GitHub({
        clientId: env.GITHUB_CLIENT_ID,
        clientSecret: env.GITHUB_CLIENT_SECRET,
      })
    );
  }

  return providers;
}

// Get auth secret with validation
function getAuthSecret(): string {
  if (building) {
    return 'build-placeholder';
  }

  const secret = env.AUTH_SECRET;

  if (!secret) {
    if (env.NODE_ENV === 'production') {
      throw new Error('AUTH_SECRET must be set in production');
    }
    console.warn('⚠️  WARNING: AUTH_SECRET not set. Using development fallback.');
    return 'dev-secret-change-in-production';
  }

  return secret;
}

export const { handle, signIn, signOut } = SvelteKitAuth({
  adapter: PrismaAdapter(prisma),
  providers: buildProviders(),
  secret: getAuthSecret(),
  trustHost: true,
  session: {
    strategy: 'jwt', // Required for Credentials provider
  },
  pages: {
    signIn: '/login',
  },
  events: {
    async createUser({ user }) {
      // Grant registration credits for OAuth users (fire-and-forget)
      if (!user.id) return;
      try {
        await fetch(`${BACKEND_URL}/api/admin/internal/grant-registration-credits`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
          },
          body: JSON.stringify({ userId: user.id }),
        });
      } catch (error) {
        console.error('Failed to grant registration credits for OAuth user:', error);
      }
    },
  },
  callbacks: {
    async jwt({ token, user, account, trigger }) {
      // Auth.js reports trigger === 'signUp' only on the request that creates
      // the adapter user (OAuth). Stamped so the client can fire the GA4
      // "Signup" conversion; self-expires via the freshness check below, since
      // the JWT itself is long-lived.
      if (trigger === 'signUp') {
        token.signupAt = Date.now();
        token.signupMethod = account?.provider ?? 'oauth';
      }
      // On sign in, add user info to token
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.image = user.image;
        // For credentials auth, role comes from the login response
        // For OAuth users, look up role from DB
        if ((user as any).role) {
          token.role = (user as any).role;
        } else if (user.id) {
          const dbUser = await prisma.user.findUnique({
            where: { id: user.id },
            select: { role: true },
          });
          token.role = dbUser?.role || 'USER';
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Add user id and role to session from JWT token
      if (session.user && token) {
        session.user.id = token.id as string;
        session.user.email = token.email as string;
        session.user.name = token.name as string | null;
        session.user.image = token.image as string | null;
        session.user.role = token.role as string | undefined;
        // Surfaced only for the first minute after account creation, so a
        // stale token can never re-report the conversion.
        const signupAt = token.signupAt as number | undefined;
        session.user.freshSignup =
          signupAt && Date.now() - signupAt < SIGNUP_FRESHNESS_MS
            ? ((token.signupMethod as string) ?? 'oauth')
            : undefined;
      }
      return session;
    },
  },
});

/** Returns which OAuth providers have valid credentials configured. */
export function getAvailableProviders() {
  return {
    google: !!(env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET),
    github: !!(env.GITHUB_CLIENT_ID && env.GITHUB_CLIENT_SECRET),
  };
}

// Type augmentation for session
declare module '@auth/core/types' {
  interface Session {
    user: {
      id: string;
      email: string;
      name?: string | null;
      image?: string | null;
      role?: string;
      /** Provider name for a just-created account; drives the GA4 "Signup" event. */
      freshSignup?: string;
    };
  }
}
