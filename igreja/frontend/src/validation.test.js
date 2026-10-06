import { describe, expect, it } from "vitest";
import { formatPhone, validateMemberForm } from "./validation.js";

describe("member validation", () => {
  it("formats Brazilian mobile numbers while typing", () => {
    expect(formatPhone("11999999999")).toBe("(11) 99999-9999");
    expect(formatPhone("1133334444")).toBe("(11) 3333-4444");
  });

  it("rejects invalid values before submitting", () => {
    expect(validateMemberForm({ full_name: "A", email: "wrong", phone: "1199" })).toEqual({
      full_name: "Informe o nome completo.",
      email: "Informe um e-mail válido.",
      phone: "Informe um telefone válido com DDD.",
    });
  });

  it("accepts a valid member with optional contact fields", () => {
    expect(validateMemberForm({ full_name: "Ana Souza", email: "ana@example.com", phone: "(11) 99999-9999" })).toEqual({});
  });
});