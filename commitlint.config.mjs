/* eslint-disable import/no-extraneous-dependencies */
import { maxLineLength } from "@commitlint/ensure";

const bodyMaxLineLength = 100;

const validateBodyMaxLengthIgnoringDeps = (parsedCommit) => {
  const { type, scope, body } = parsedCommit;
  const isDepsCommit =
    type === "chore" && (scope === "deps" || scope === "deps-dev");

  return [
    isDepsCommit || !body || maxLineLength(body, bodyMaxLineLength),
    `body's lines must not be longer than ${bodyMaxLineLength}`,
  ];
};

export default {
  extends: ["@commitlint/config-conventional"],
  plugins: ["commitlint-plugin-function-rules"],
  rules: {
    "body-max-line-length": [0],
    "function-rules/body-max-line-length": [
      2,
      "always",
      validateBodyMaxLengthIgnoringDeps,
    ],
  },
};
