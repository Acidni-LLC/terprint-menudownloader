---
description: 'TypeScript development standards for Acidni LLC projects'
applyTo: '**/*.ts, **/*.tsx'
---

# TypeScript Development Instructions

Instructions for TypeScript development in Acidni LLC projects, targeting TypeScript 5.x with strict type checking.

## Project Context

- Target: TypeScript 5.x
- Output: ES2022
- Primary use cases: VS Code extensions, Power BI visuals, web frontends
- Package manager: npm (prefer over yarn/pnpm for consistency)

## Compiler Configuration

```json
// tsconfig.json - Strict configuration
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

## Type Safety Rules

### Never Use `any`

```typescript
// ✅ Good - Explicit types
interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}

function processResponse<T>(response: ApiResponse<T>): T | null {
  if (response.success) {
    return response.data;
  }
  console.error(response.error);
  return null;
}

// ❌ Bad - Using any defeats type safety
function processResponse(response: any): any {
  return response.data;
}
```

### Use `unknown` for External Data

```typescript
// ✅ Good - Validate unknown data before use
async function fetchData(url: string): Promise<UserData> {
  const response = await fetch(url);
  const data: unknown = await response.json();
  
  if (!isUserData(data)) {
    throw new Error('Invalid response format');
  }
  
  return data;
}

function isUserData(data: unknown): data is UserData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'id' in data &&
    'name' in data
  );
}
```

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | `kebab-case.ts` | `user-service.ts` |
| Classes | `PascalCase` | `UserService` |
| Interfaces | `PascalCase` | `UserData` |
| Functions | `camelCase` | `getUserById` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Types | `PascalCase` | `UserStatus` |

**Note**: Do NOT prefix interfaces with `I` (e.g., use `User` not `IUser`).

## Interface vs Type

```typescript
// Use interfaces for object shapes (extendable)
interface User {
  id: string;
  name: string;
}

interface Admin extends User {
  permissions: string[];
}

// Use types for unions, primitives, and computed types
type UserStatus = 'active' | 'inactive' | 'pending';
type UserId = string;
type UserMap = Record<string, User>;
```

## Error Handling

```typescript
// Define custom error classes
class ApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly code: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// Use Result type for operations that can fail
type Result<T, E = Error> = 
  | { success: true; data: T }
  | { success: false; error: E };

async function fetchUser(id: string): Promise<Result<User, ApiError>> {
  try {
    const response = await fetch(`/api/users/${id}`);
    if (!response.ok) {
      return {
        success: false,
        error: new ApiError('User not found', response.status, 'NOT_FOUND')
      };
    }
    const data = await response.json() as User;
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: new ApiError('Network error', 0, 'NETWORK_ERROR')
    };
  }
}
```

## Async/Await Patterns

```typescript
// ✅ Good - Proper async error handling
async function processItems(items: string[]): Promise<ProcessResult[]> {
  const results = await Promise.allSettled(
    items.map(item => processItem(item))
  );
  
  return results.map((result, index) => {
    if (result.status === 'fulfilled') {
      return { item: items[index], success: true, data: result.value };
    }
    return { item: items[index], success: false, error: result.reason };
  });
}

// ❌ Bad - Unhandled promise rejection
async function processItems(items: string[]): Promise<void> {
  items.forEach(async item => {
    await processItem(item); // Unhandled if this throws
  });
}
```

## Project Structure

```
project/
├── src/
│   ├── index.ts                # Main entry point
│   ├── types/
│   │   └── index.ts           # Shared type definitions
│   ├── services/
│   │   └── user-service.ts
│   ├── utils/
│   │   └── validation.ts
│   └── constants.ts
├── tests/
│   ├── unit/
│   └── integration/
├── tsconfig.json
├── package.json
└── README.md
```

## VS Code Extension Patterns

For ACCM and other VS Code extensions:

```typescript
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext): void {
  // Register commands
  const disposable = vscode.commands.registerCommand(
    'acidni.myCommand',
    async () => {
      await executeMyCommand();
    }
  );
  
  context.subscriptions.push(disposable);
}

export function deactivate(): void {
  // Cleanup resources
}
```

## Power BI Visual Patterns

For Terprint Power BI visuals:

```typescript
import powerbi from 'powerbi-visuals-api';
import { FormattingSettingsService } from 'powerbi-visuals-utils-formattingmodel';

export class TerpeneRadar implements powerbi.extensibility.visual.IVisual {
  private target: HTMLElement;
  private formattingSettings: FormattingSettingsService;

  constructor(options: powerbi.extensibility.visual.VisualConstructorOptions) {
    this.target = options.element;
    this.formattingSettings = new FormattingSettingsService();
  }

  public update(options: powerbi.extensibility.visual.VisualUpdateOptions): void {
    // Render visualization
  }
}
```

## Code Style

- Use ESLint with TypeScript parser
- Use Prettier for formatting
- Maximum line length: 100 characters
- Use template literals for string interpolation
- Prefer `const` over `let` when value won't change
- Use optional chaining (`?.`) and nullish coalescing (`??`)

```typescript
// ✅ Good - Modern TypeScript features
const userName = user?.profile?.name ?? 'Anonymous';

// ❌ Bad - Verbose null checking
const userName = user && user.profile && user.profile.name 
  ? user.profile.name 
  : 'Anonymous';
```
