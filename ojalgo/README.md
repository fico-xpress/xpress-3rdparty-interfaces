# ojAlgo Integration

Examples demonstrating FICO&reg; Xpress integration with [ojAlgo](https://www.ojalgo.org/).

## Examples

| Example | Description | Notes |
|---------|-------------|-------|
| [PortfolioOjAlgo.java](src/main/java/PortfolioOjAlgo.java) | Portfolio optimization as a MIQP: quadratic objective, cardinality constraints and solver parameters | Same problem and data as the Python examples, see [data/](../data/) |

## About ojAlgo

ojAlgo is an open source, pure Java library for mathematical optimization, used from Java, Kotlin, Scala and other JVM languages. Its modeling API, `ExpressionsBasedModel`, builds models as plain Java objects &mdash; no modeling language or model files &mdash; and the integration module [ojalgo-xpress](https://central.sonatype.com/artifact/org.ojalgo/ojalgo-xpress) hands them to Xpress through the Xpress Java API, in memory.

Key features:
- One Maven dependency, MIT licensed
- LP, QP and MIP, including MIQP, through Xpress
- Model options mapped to Xpress controls: time limit (`MAXTIME`), threads, tolerances and MIP gap (`MIPRELSTOP`, `MIPABSSTOP`)
- Any other Xpress control set with a configurator, as in the example (`HEUREMPHASIS`)
- Infeasible results carry an infeasibility certificate (Farkas), built from Xpress's dual ray and verified against the model

Registering Xpress takes one line, `ExpressionsBasedModel.addIntegration(SolverXpress.INTEGRATION)`; from then on Xpress solves the models. More: [FICO Xpress from Java with ojAlgo](https://www.ojalgo.org/mathematical-optimisation/xpress/).

## Requirements

- Java 11+ and Maven
- FICO Xpress installed, with a valid license (Community Edition or full license)
- Two environment variables:
  - `XPRESSDIR`: the Xpress installation directory, the one containing `lib/xprs.jar`
  - `XPAUTH_PATH`: the license file, typically `$XPRESSDIR/bin/xpauth.xpr`

The project takes `xprs.jar` from `$XPRESSDIR/lib` and puts the same directory on the JVM's library path for Xpress's native libraries.

## Running the Example

```bash
cd xpress-3rdparty-interfaces/ojalgo
mvn compile exec:exec
```

On recent JDKs, loading Xpress's native libraries prints a warning about restricted methods; adding `--enable-native-access=ALL-UNNAMED` to the JVM arguments in `pom.xml` silences it (Java 17+).
