# rewrite-cucumber-jvm: Cucumber-JVM upgrades

Rules of the Cucumber-JVM upgrades (`org.openrewrite.cucumber.jvm.UpgradeCucumber7x` and the steps it includes).
Read the resolved `cucumber-java`, `cucumber-junit-platform-engine` and `junit-platform-suite` versions first.

Check, for every rule here: run the Cucumber suite and compare the number of scenarios that ran with the number
before the Migration. A suite that selects no features, or a runner the JUnit Platform does not find, runs nothing
and passes.

## testing/cucumber-java8-glue-not-migrated

A cucumber-java8 lambda glue call (`Given(..)`, `When(..)`, `Before(..)`, ...) could not be moved to an annotated
cucumber-java method, for example because the lambda captures state or its expression is not a literal.

- Write the step as a method annotated with `@Given`, `@When`, ... in the same class, with the lambda body as the
  method body and the lambda parameters as method parameters.
- Remove the `En` interface and the cucumber-java8 dependency once no lambda glue is left.

## testing/cucumber-java8-captured-local-not-migrated

The migrated step methods use local variables of the constructor or method that held the lambdas, and those locals
cannot become fields as they are (for example they are reassigned). The code does not compile until handled.

- Turn each local into a field that the step methods read, and initialize it where the local was; keep the
  initialization order.
- Cucumber makes a new glue instance per scenario, so a field is per scenario as the local was.

## testing/cucumber-options-property-not-migrated

Cucumber-JVM 6 no longer reads `cucumber.options`, so its options are silently ignored. The property was left as it
was, because an option has no individual property (such as `--threads`), or an individual property is already set.

- Move each option to its `cucumber.*` property (`--tags` to `cucumber.filter.tags`, `--glue` to `cucumber.glue`,
  `--plugin` to `cucumber.plugin`, ...) in the same file, and delete `cucumber.options`.
- `--threads`: use the JUnit Platform parallel execution properties (`cucumber.execution.parallel.enabled`).
- An individual property already set: keep one value, and say in the note which one won.

## testing/cucumber-runner-not-migrated

A class with `@RunWith(Cucumber.class)` kept the JUnit 4 runner: it extends another class (which may contribute
`@CucumberOptions`), or an option cannot be carried over (it refers to a constant, it is not a literal, or it has
no JUnit Platform counterpart). The message names the reason.

- Write the `@Suite` class by hand: `@IncludeEngines("cucumber")`, `@SelectClasspathResource` for the features, and
  `@ConfigurationParameter` for each option. Inline a constant's value or keep the constant in the parameter value.
- Set `cucumber.glue` explicitly to the runner's package when no glue was configured: the JUnit 4 runner looked
  there by default, the engine looks on the whole class path.
- `@BeforeClass` and `@AfterClass` methods become `@BeforeSuite` and `@AfterSuite`.

## testing/cucumber-type-registry-configurer-not-migrated

Cucumber-JVM 7 removed `TypeRegistryConfigurer`. The class kept it, because a registration in
`configureTypeRegistry` cannot be converted, or the class has no body to convert. It does not compile until handled.

- Convert each registration to an annotated glue method: `@ParameterType` for a `ParameterType`, `@DataTableType`
  for a table entry or row transformer, `@DocStringType` for a doc string type, `@DefaultParameterTransformer` and
  `@DefaultDataTableEntryTransformer` for the defaults.
- Put the methods in a glue class, and delete the configurer.
