export function formatPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits ? `(${digits}` : "";
  if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}${digits.length > 6 ? `-${digits.slice(6)}` : ""}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

export function validateMemberForm(values) {
  const errors = {};
  if (values.full_name.trim().length < 2) errors.full_name = "Informe o nome completo.";
  if (values.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email.trim())) errors.email = "Informe um e-mail válido.";
  const phoneDigits = values.phone.replace(/\D/g, "");
  if (phoneDigits && ![10, 11].includes(phoneDigits.length)) errors.phone = "Informe um telefone válido com DDD.";
  return errors;
}
