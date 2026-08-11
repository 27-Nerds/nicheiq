import { readFileSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

export interface SelectionBoundaryRule {
  target: string;
  allow: readonly string[];
}

export interface SelectionBoundaryOptions {
  projectRoot?: string;
  rules?: readonly SelectionBoundaryRule[];
}

export interface SelectionBoundaryViolation {
  file: string;
  line: number;
  message: string;
}

const RAW_LOADER_NAME = 'getPreviewReportForJob';

const DEFAULT_RULES: readonly SelectionBoundaryRule[] = [
  {
    target: 'src/services/selectionBoundary/privateAssetReader.ts',
    allow: [
      'src/services/assetService.ts',
      'src/services/selectionBoundary/rawPreviewReport.ts',
    ],
  },
  {
    target: 'src/services/selectionBoundary/rawPreviewReport.ts',
    allow: [
      'src/routes/discoveryShares.ts',
      'src/routes/jobs.ts',
      'src/routes/selectionChallenges.ts',
      'src/routes/selectionExperiments.ts',
      'src/routes/selectionFinalDecisions.ts',
      'src/services/currentSelectionContext.ts',
    ],
  },
];

type DependencyKind = 'import' | 'dynamic import' | 'require' | 're-export';

interface Dependency {
  kind: DependencyKind;
  node: ts.Node;
  specifier: string;
  resolved: string | null;
}

function normalized(path: string): string {
  return resolve(path).split(sep).join('/');
}

function productionSource(path: string): boolean {
  const unix = path.split(sep).join('/');
  return path.endsWith('.ts')
    && !path.endsWith('.d.ts')
    && !unix.includes('/__tests__/')
    && !unix.includes('/tests/');
}

function moduleText(node: ts.Expression): string | null {
  return ts.isStringLiteralLike(node) ? node.text : null;
}

function dependencies(
  sourceFile: ts.SourceFile,
  compilerOptions: ts.CompilerOptions,
): { edges: Dependency[]; unverifiable: ts.Node[] } {
  const edges: Dependency[] = [];
  const unverifiable: ts.Node[] = [];

  const add = (kind: DependencyKind, node: ts.Node, specifier: string) => {
    const resolvedModule = ts.resolveModuleName(
      specifier,
      sourceFile.fileName,
      compilerOptions,
      ts.sys,
    ).resolvedModule;
    edges.push({
      kind,
      node,
      specifier,
      resolved: resolvedModule ? normalized(resolvedModule.resolvedFileName) : null,
    });
  };

  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteralLike(node.moduleSpecifier)) {
      add('import', node, node.moduleSpecifier.text);
    } else if (
      ts.isExportDeclaration(node)
      && node.moduleSpecifier
      && ts.isStringLiteralLike(node.moduleSpecifier)
    ) {
      add('re-export', node, node.moduleSpecifier.text);
    } else if (ts.isCallExpression(node)) {
      const isDynamicImport = node.expression.kind === ts.SyntaxKind.ImportKeyword;
      const isRequire = ts.isIdentifier(node.expression) && node.expression.text === 'require';
      if (isDynamicImport || isRequire) {
        const argument = node.arguments[0];
        const specifier = argument ? moduleText(argument) : null;
        if (specifier === null) {
          unverifiable.push(node);
        } else {
          add(isDynamicImport ? 'dynamic import' : 'require', node, specifier);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return { edges, unverifiable };
}

function lineOf(sourceFile: ts.SourceFile, node: ts.Node): number {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function exportsImportedRestrictedBinding(
  sourceFile: ts.SourceFile,
  restrictedImports: ReadonlySet<string>,
): ts.Node[] {
  const violations: ts.Node[] = [];
  for (const statement of sourceFile.statements) {
    if (!ts.isExportDeclaration(statement) || statement.moduleSpecifier || !statement.exportClause) {
      continue;
    }
    if (ts.isNamedExports(statement.exportClause)) {
      for (const element of statement.exportClause.elements) {
        const localName = (element.propertyName ?? element.name).text;
        if (restrictedImports.has(localName)) violations.push(element);
      }
    }
  }
  return violations;
}

export function checkSelectionBoundary(
  options: SelectionBoundaryOptions = {},
): SelectionBoundaryViolation[] {
  const projectRoot = normalized(options.projectRoot ?? resolve(dirname(fileURLToPath(import.meta.url)), '../..'));
  const configPath = resolve(projectRoot, 'tsconfig.json');
  const config = ts.readConfigFile(configPath, path => readFileSync(path, 'utf8'));
  if (config.error) {
    throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
  }
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, projectRoot);
  const sourcePaths = parsed.fileNames.filter(productionSource).map(normalized);
  const sourcePathSet = new Set(sourcePaths);
  const rules = (options.rules ?? DEFAULT_RULES).map(rule => ({
    target: normalized(resolve(projectRoot, rule.target)),
    allow: new Set(rule.allow.map(path => normalized(resolve(projectRoot, path)))),
  }));
  const violations: SelectionBoundaryViolation[] = [];
  const checkerFile = normalized(fileURLToPath(import.meta.url));

  for (const fileName of sourcePaths) {
    const text = readFileSync(fileName, 'utf8');
    const sourceFile = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true);
    const fileRelative = relative(projectRoot, fileName).split(sep).join('/');
    const { edges, unverifiable } = dependencies(sourceFile, parsed.options);

    for (const node of unverifiable) {
      violations.push({
        file: fileRelative,
        line: lineOf(sourceFile, node),
        message: 'Non-literal import()/require() is forbidden because the selection boundary cannot resolve it.',
      });
    }

    const importedRestrictedBindings = new Set<string>();
    for (const edge of edges) {
      if (!edge.resolved || !sourcePathSet.has(edge.resolved)) continue;
      for (const rule of rules) {
        if (edge.resolved !== rule.target) continue;
        const allowed = rule.allow.has(fileName);
        if (!allowed || edge.kind === 're-export') {
          violations.push({
            file: fileRelative,
            line: lineOf(sourceFile, edge.node),
            message: `${edge.kind} of private selection module ${relative(projectRoot, rule.target).split(sep).join('/')} is forbidden.`,
          });
        }
        if (allowed && edge.kind === 'import' && ts.isImportDeclaration(edge.node)) {
          const clause = edge.node.importClause;
          if (clause?.name) importedRestrictedBindings.add(clause.name.text);
          const bindings = clause?.namedBindings;
          if (bindings && ts.isNamespaceImport(bindings)) {
            importedRestrictedBindings.add(bindings.name.text);
          } else if (bindings) {
            for (const element of bindings.elements) importedRestrictedBindings.add(element.name.text);
          }
        }
      }
    }

    for (const node of exportsImportedRestrictedBinding(sourceFile, importedRestrictedBindings)) {
      violations.push({
        file: fileRelative,
        line: lineOf(sourceFile, node),
        message: 'An allowlisted private selection import must not be re-exported.',
      });
    }

    const rawLoaderRule = rules.find(rule => rule.target.endsWith('/rawPreviewReport.ts'));
    const rawNameAllowed = fileName === checkerFile
      || rawLoaderRule?.target === fileName
      || rawLoaderRule?.allow.has(fileName);
    if (!rawNameAllowed) {
      const visitRawName = (node: ts.Node): void => {
        if (
          (ts.isIdentifier(node) || ts.isStringLiteralLike(node))
          && node.text === RAW_LOADER_NAME
        ) {
          violations.push({
            file: fileRelative,
            line: lineOf(sourceFile, node),
            message: `${RAW_LOADER_NAME} is private; use loadCurrentSelectionContext().`,
          });
          return;
        }
        ts.forEachChild(node, visitRawName);
      };
      visitRawName(sourceFile);
    }
  }

  return violations;
}

function main(): void {
  const violations = checkSelectionBoundary();
  if (violations.length === 0) {
    console.log('Selection boundary: OK');
    return;
  }
  for (const violation of violations) {
    console.error(`${violation.file}:${violation.line} ${violation.message}`);
  }
  process.exitCode = 1;
}

if (process.argv[1] && normalized(process.argv[1]) === normalized(fileURLToPath(import.meta.url))) {
  main();
}
